"""Fixed-step M8 monitoring. Generation endpoints never score teacher logits."""
import asyncio
from dataclasses import dataclass
from datetime import datetime,timezone
import json
import os
from pathlib import Path

from rlm_opsd.detectors import analyze_trajectory,aggregate_behavior,write_behavior_report
from rlm_opsd.prompts import ChatRenderer
from rlm_opsd.training.backend import load_backend,require_cuda
from rlm_opsd.training.config import OpsdConfig
from rlm_opsd.training.runner import verify_gate,cached_snapshot
from rlm_opsd.training.samples import samples_from_rollout
from .gate import GateClient,write_json,append_json
from .preflight import sha256,safe_error
from .monitor_config import MonitorConfig
from .metrics import score_trajectory
from .scoring import load_adapter,score_samples,token_offsets


@dataclass
class MonitorPlan:
    training: object
    gate: object
    gate_plan: object
    renderer: object
    snapshot: Path
    answers: dict
    provenance: dict


def prepare_monitor(config):
    if sha256(config.checkpoint)!=config.checkpoint_sha256:raise ValueError('checkpoint hash differs')
    training=OpsdConfig.from_toml(config.training_config)
    gate,plan=verify_gate(training)
    if (config.student_endpoint.base_url,config.student_endpoint.served_model) in {
        (e.base_url,e.served_model) for e in (gate.root_endpoint,gate.frozen_endpoint)}:
        raise ValueError('student checkpoint endpoint must be distinct from frozen base identity')
    if config.student_endpoint.api_key_var and not os.environ.get(config.student_endpoint.api_key_var):
        raise ValueError('student endpoint API-key environment variable is missing')
    require_cuda();snapshot=cached_snapshot(training)
    renderer=ChatRenderer(plan.prompt_config)
    rows=[json.loads(line) for line in gate.manifest_path.read_text().splitlines()]
    answers={r['task_id']:(r['answer'],r['answer_type']) for r in rows}
    provenance={**plan.provenance, 'checkpoint_sha256':config.checkpoint_sha256,
        'checkpoint_step':config.checkpoint_step,
        'training_config_sha256':sha256(config.training_config),
        'endpoint_identity':'operator-declared base/checkpoint/template identity; response aliases checked'}
    return MonitorPlan(training,gate,plan,renderer,snapshot,answers,provenance)


def check_monitor(path):
    try:
        config=MonitorConfig.from_yaml(path)
        prepare_monitor(config)
        return dict(status='ready',blockers=[],model_requests_sent=False)
    except Exception as exc:
        return dict(status='not_run',blockers=[safe_error(exc)],model_requests_sent=False)


def sampling(config,plan,seed):
    return dict(temperature=config.temperature,seed=seed,max_tokens=plan.gate_plan.harness_config.max_tokens_per_turn,
        top_p=1.,presence_penalty=0.,frequency_penalty=0.,logprobs=True,
        extra_body={'return_token_ids':True,'top_k':-1,'min_p':0.,'repetition_penalty':1.})


async def collect_episode(config,plan,task,phase,seed,root,frozen,output):
    from datasets import Dataset
    from rlm_opsd.harness import RLMOpsdEnv
    variant='teacher' if phase=='teacher' else 'student'
    env=RLMOpsdEnv(config=plan.gate_plan.harness_config,prompt_config=plan.gate_plan.prompt_config,
        prompt_builder=plan.gate_plan.prompt_builder,prompt_variant=variant,
        frozen_client=frozen,frozen_model=plan.gate.frozen_endpoint.served_model,
        log_dir=output/'trajectories'/phase,
        dataset=Dataset.from_list([dict(question=task['info']['query'],answer='')]))
    before_errors=len(frozen.errors)
    root.context=frozen.context=dict(task_id=task['info']['task_id'],phase=phase,seed=seed)
    try:
        async with asyncio.timeout(plan.gate.episode_timeout_s):
            state=await env.rollout(input=task,client=root,model=root.endpoint.served_model,
                                    sampling_args=sampling(config,plan,seed))
        if state.get('error') or len(frozen.errors)>before_errors or state['opsd_episode'].infrastructure_errors:
            raise RuntimeError('generation or harness infrastructure failed')
        path=Path(state['opsd_trajectory_path'])
        rollout=dict(error=None,sampling_args={'temperature':config.temperature},
                     trajectory=[dict(tokens=s.get('tokens')) for s in state['trajectory']])
        return path,rollout
    finally:await env.teardown_rlm()


def score_episode(config,plan,backend,task,rollout,path):
    pair=plan.gate_plan.prompt_builder.build(query=task['info']['query'],context=task['info']['context'],
                                             config=plan.gate_plan.harness_config)
    samples=samples_from_rollout(rollout,plan.renderer.prefixes(pair),max_seq_len=plan.training.max_seq_len)
    scores=score_samples(backend.model,samples,chunk_size=plan.training.jsd_chunk_size,api=backend.trainer.api)
    turns=[]
    for index,(step,score) in enumerate(zip(rollout['trajectory'],scores,strict=True)):
        tokens=step['tokens'];mapping=token_offsets(plan.renderer.tokenizer,tokens['completion_ids'])
        selected=[offset for offset,keep in zip(mapping['offsets'],tokens['completion_mask'],strict=True) if keep]
        if len(selected)!=len(score['kl']):raise ValueError('KL offsets differ from selected targets')
        turns.append(dict(turn_index=index,text=mapping['text'],offsets=selected,values=score['kl'],
                          trajectory_path=str(path)))
    if not any(t['values'] for t in turns):raise ValueError('evaluation has no scored assistant targets')
    return turns


async def run_monitor(config,output_dir):
    from .monitor_reports import summarize_divergence,write_monitor_reports,seal_evidence
    output=Path(output_dir).resolve()
    if output.exists():raise FileExistsError('monitor output already exists')
    if config.checkpoint_step%config.eval_interval:
        return dict(status='not_due',model_requests_sent=False,checkpoint_step=config.checkpoint_step)
    plan=prepare_monitor(config)
    output.mkdir(parents=True,exist_ok=False)
    meta=dict(status='running',config=config.model_dump(mode='json'),provenance=plan.provenance,
              started_at=datetime.now(timezone.utc).isoformat())
    write_json(output/'run.json',meta)
    (output/'requests.jsonl').touch();(output/'records.jsonl').touch()
    # Snapshot reporting settings/labels; none of these labels go to generation.
    write_json(output/'detectors.json',plan.gate_plan.detector_config.model_dump(mode='json'))
    selected_ids=[t['info']['task_id'] for t in plan.gate_plan.inputs]
    write_json(output/'answers.json',{i:plan.answers[i] for i in selected_ids})
    (output/'rollouts').mkdir()
    records=[];turns=[];clients=[];backend=None;cancelled=None
    result=dict(status='error',kind='not_loaded',errors=[],provenance=plan.provenance)
    try:
        backend_config=plan.training
        backend=load_backend(backend_config,plan.snapshot,output)
        load_adapter(backend.model,config.checkpoint,config.checkpoint_sha256,api=backend.trainer.api)
        result['kind']='pretrained_model_evaluation' if backend.kind=='pretrained_model_smoke' else backend.kind
        base=GateClient(plan.gate.root_endpoint,plan.gate.request_timeout_s,'base',output/'requests.jsonl');clients.append(base)
        student=GateClient(config.student_endpoint,plan.gate.request_timeout_s,'student',output/'requests.jsonl');clients.append(student)
        frozen=GateClient(plan.gate.frozen_endpoint,plan.gate.request_timeout_s,'frozen',output/'requests.jsonl');clients.append(frozen)
        for task_index,task in enumerate(plan.gate_plan.inputs):
            for phase,root in (('before',base),('teacher',base),('after',student)):
                path,rollout=await collect_episode(config,plan,task,phase,config.seed+task_index,root,frozen,output)
                raw=json.loads(path.read_text())
                score=score_trajectory(raw,*plan.answers[task['info']['task_id']])
                record=dict(phase=phase,trajectory_path=str(path),analysis=analyze_trajectory(raw,plan.gate_plan.detector_config),
                            task_success=score==1.,task_score=score)
                records.append(record);append_json(output/'records.jsonl',{**record,'trajectory_path':str(path.relative_to(output))})
                if phase=='after':
                    write_json(output/'rollouts'/(path.stem+'.json'),rollout)
                    turns.extend(score_episode(config,plan,backend,task,rollout,path))
        metrics=dict(behavior=aggregate_behavior(records),divergence=summarize_divergence(turns,top_k=config.kl_top_k))
        write_json(output/'token-scores.json',turns)
        write_json(output/'metrics.json',metrics)
        result.update(status='completed',completed_episodes=len(records))
    except (Exception,asyncio.CancelledError) as exc:
        result['errors'].append(dict(phase='monitor',error_type=type(exc).__name__))
        if isinstance(exc,asyncio.CancelledError):cancelled=exc
    finally:
        for client in clients:
            try:await client.close()
            except (Exception,asyncio.CancelledError) as exc:
                result['errors'].append(dict(phase='cleanup',error_type=type(exc).__name__))
                if isinstance(exc,asyncio.CancelledError):cancelled=exc
        if backend is not None:
            try:backend.close()
            except Exception as exc:result['errors'].append(dict(phase='backend_cleanup',error_type=type(exc).__name__))
    if result['errors']:result['status']='error'
    try:
        write_behavior_report(records,output,source_label=config.run_label)
        write_monitor_reports(output,config,records,result)
    except Exception as exc:
        result['status']='error';result['errors'].append(dict(phase='report',error_type=type(exc).__name__))
    meta.update(status=result['status'],kind=result['kind'],finished_at=datetime.now(timezone.utc).isoformat())
    write_json(output/'run.json',meta)
    result['evidence']=seal_evidence(output)
    write_json(output/'monitor.json',result)
    if cancelled:raise cancelled
    return result
