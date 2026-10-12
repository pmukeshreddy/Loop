"""Guarded generation -> aligned local distillation -> LoRA checkpoint smoke."""
import asyncio
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from rlm_opsd.detectors import analyze_trajectory,aggregate_behavior
from rlm_opsd.eval import GateConfig,prepare_gate,evaluate_gate
from rlm_opsd.eval.gate import GateClient,write_json
from rlm_opsd.eval.preflight import sha256,safe_error
from rlm_opsd.prompts import PromptConfig,PromptBuilder,ChatRenderer
from rlm_opsd.tasks.build import load_tasks
from .backend import require_cuda,load_backend
from .config import MODEL_PINS
from .samples import samples_from_rollout


def contained(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('evidence path escapes run directory')
    return path


def verify_gate(config):
    if config.gate_dir is None:raise ValueError('a passed real teacher gate is required')
    directory=config.gate_dir
    gate=json.loads((directory/'gate.json').read_text())
    if any(word in str(gate.get('run_label','')).lower() for word in ('fixture','synthetic')):
        raise ValueError('fixture/synthetic gate reports cannot authorize training')
    metadata=json.loads((directory/'run.json').read_text())
    gate_config=GateConfig.from_yaml(config.gate_config)
    if (gate_config.base_model,gate_config.revision)!=(config.base_model,config.revision):
        raise ValueError('gate model/revision differs from the smoke model')
    if sha256(gate_config.prompt_config)!=sha256(config.prompt_config):
        raise ValueError('gate and smoke prompt configs differ')
    plan=prepare_gate(gate_config)
    settings=gate_config.model_dump(mode='json')
    settings_hash=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()
    if metadata.get('config_sha256')!=settings_hash or metadata.get('provenance')!=plan.provenance:
        raise ValueError('gate settings/input provenance is stale or inconsistent')
    expected={(phase,item['info']['task_id']) for item in plan.inputs for phase in ('before','teacher')}
    task_info={item['info']['task_id']:item['info'] for item in plan.inputs}
    if (gate.get('status')!='passed' or metadata.get('status')!='passed' or gate.get('errors')
            or gate.get('completed_episodes')!=len(expected) or gate.get('planned_episodes')!=len(expected)):
        raise ValueError('teacher gate did not pass a complete real paired run')
    records=[];seen=set()
    for source in gate.get('trajectories',[]):
        pair=(source['phase'],source['task_id'])
        if pair not in expected or pair in seen:raise ValueError('unexpected or duplicate gate trajectory')
        seen.add(pair)
        path=contained(directory,source['path']);raw=json.loads(path.read_text())
        if raw['task_id']!=source['task_id']:raise ValueError('gate trajectory identity differs')
        variant='student' if source['phase']=='before' else 'teacher'
        if raw.get('prompt_variant')!=variant:
            raise ValueError('gate trajectory prompt variant differs from its phase')
        info=task_info[source['task_id']]
        if any(raw.get(key)!=info.get(key) for key in ('family','domain','tags','size_bucket')):
            raise ValueError('gate trajectory task metadata differs from current inputs')
        records.append(dict(phase=source['phase'],trajectory_path=str(path),analysis=analyze_trajectory(raw,plan.detector_config)))
    if seen!=expected or evaluate_gate(aggregate_behavior(records),gate_config.criteria)['status']!='passed':
        raise ValueError('gate trajectory evidence no longer passes configured criteria')
    requests=[json.loads(line) for line in (directory/'requests.jsonl').read_text().splitlines()]
    if not requests or any(r.get('status')!='completed' for r in requests):
        raise ValueError('gate generation request evidence is missing or failed')
    root_pairs={(r.get('phase'),r.get('task_id')) for r in requests if r.get('role')=='root'}
    if root_pairs!=expected:raise ValueError('gate generation requests do not cover all pairs')
    for request in requests:
        if request.get('role') not in ('root','frozen'):raise ValueError('unknown gate request role')
        endpoint=gate_config.root_endpoint if request['role']=='root' else gate_config.frozen_endpoint
        if request.get('response_model')!=endpoint.served_model:raise ValueError('gate endpoint model mismatch')
    return gate_config,plan


def objective_metadata(config):
    return dict(kind='full_vocab_jsd',beta=config.jsd_beta,token_gate=config.token_gate,
                token_gate_k=config.token_gate_k,temperature=config.temperature)


def verify_small_smoke(config):
    if config.stage!='27b':return
    if config.small_smoke_dir is None:raise ValueError('run the pinned small smoke before 27B')
    root=config.small_smoke_dir
    record=json.loads((root/'smoke.json').read_text())
    if (record.get('status')!='completed' or record.get('kind')!='pretrained_model_smoke'
            or record.get('base_quantization')!='nf4'
            or record.get('stage')!='small'
            or (record.get('base_model'),record.get('revision'))!=MODEL_PINS['small']
            or record.get('metrics',{}).get('updated') is not True
            or record.get('metrics',{}).get('assistant_tokens',0)<=0):
        raise ValueError('a successful pinned pretrained small-model smoke is required')
    if sha256(contained(root,record['checkpoint']))!=record.get('checkpoint_sha256'):
        raise ValueError('small-smoke checkpoint hash differs')
    if record.get('objective')!=objective_metadata(config):
        raise ValueError('run a small OPSD smoke with the same JSD/token-gate objective before 27B')


def cached_snapshot(config):
    from huggingface_hub import snapshot_download
    snapshot=Path(snapshot_download(config.base_model,revision=config.revision,local_files_only=True))
    if snapshot.name!=config.revision:raise ValueError('cached snapshot revision differs')
    index=snapshot/'model.safetensors.index.json'
    shards=set(json.loads(index.read_text())['weight_map'].values()) if index.exists() else {'model.safetensors'}
    # HF snapshot entries normally symlink into ../.. /blobs. Validate index
    # names lexically while allowing that standard cache layout.
    if any(Path(name).is_absolute() or '..' in Path(name).parts for name in shards):
        raise ValueError('weight index path escapes snapshot')
    if not shards or any(not (snapshot/name).is_file() for name in shards):
        raise ValueError('pinned model weights are not fully cached')
    return snapshot


@dataclass
class SmokePlan:
    gate_config: object
    gate_plan: object
    task: dict
    prefixes: object
    snapshot: Path
    provenance: dict


def prepare_smoke(config):
    gate_config,gate_plan=verify_gate(config)
    verify_small_smoke(config)
    require_cuda()
    snapshot=cached_snapshot(config)
    tasks=list(load_tasks(gate_config.manifest_path,split='train'))
    if not tasks:raise ValueError('decontaminated train split is empty')
    task=next((t for t in tasks if t['info']['family']=='direct_solve'),tasks[0])
    prompt_config=PromptConfig.from_yaml(config.prompt_config)
    pair=PromptBuilder.load().build(query=task['info']['query'],context=task['info']['context'],config=gate_plan.harness_config)
    prefixes=ChatRenderer(prompt_config).prefixes(pair)
    if max(len(prefixes.student_ids),len(prefixes.teacher_ids))>=config.max_seq_len:
        raise ValueError('max_seq_len leaves no room after the teacher prefix')
    provenance=dict(gate_sha256=sha256(config.gate_dir/'gate.json'),gate_provenance=gate_plan.provenance,
        task_id=task['info']['task_id'],snapshot=str(snapshot),template_sha256=prompt_config.template_sha256,
        tokenizer_sha256=prompt_config.tokenizer_sha256,manual_version=pair.manual_version,
        endpoint_identity='operator-declared frozen initial weights; first-update smoke only')
    return SmokePlan(gate_config,gate_plan,task,prefixes,snapshot,provenance)


def check_readiness(config):
    blockers=[]
    for name,check in [('teacher gate',verify_gate),('small smoke',verify_small_smoke),
                       ('cached weights',cached_snapshot)]:
        try:check(config)
        except Exception as exc:blockers.append(name+': '+safe_error(exc))
    try:require_cuda()
    except Exception as exc:blockers.append('runtime: '+safe_error(exc))
    if not blockers:
        try:prepare_smoke(config)
        except Exception as exc:blockers.append('preflight: '+safe_error(exc))
    return dict(status='not_run' if blockers else 'ready',blockers=blockers,model_requests_sent=False)


async def collect_rollout(config,plan,output):
    from datasets import Dataset
    from rlm_opsd.harness import RLMOpsdEnv
    gate=plan.gate_config;root=None;frozen=None;env=None
    try:
        root=GateClient(gate.root_endpoint,gate.request_timeout_s,'root',output/'requests.jsonl')
        frozen=GateClient(gate.frozen_endpoint,gate.request_timeout_s,'frozen',output/'requests.jsonl')
        root.context=frozen.context=dict(task_id=plan.task['info']['task_id'],phase='student')
        env=RLMOpsdEnv(config=plan.gate_plan.harness_config,prompt_config=config.prompt_config,
            frozen_client=frozen,frozen_model=gate.frozen_endpoint.served_model,log_dir=output/'trajectories',
            dataset=Dataset.from_list([dict(question=plan.task['info']['query'],answer='')]))
        async with asyncio.timeout(gate.episode_timeout_s):
            state=await env.rollout(input=plan.task,client=root,model=gate.root_endpoint.served_model,
                sampling_args=dict(temperature=config.temperature,seed=config.seed,max_tokens=config.max_tokens,
                    top_p=1.0,presence_penalty=0.0,frequency_penalty=0.0,logprobs=True,
                    extra_body={'return_token_ids':True,'top_k':-1,'min_p':0.0,'repetition_penalty':1.0}))
        if root.errors or frozen.errors or state['opsd_episode'].infrastructure_errors:
            raise RuntimeError('generation or worker infrastructure failed')
        return dict(error=state.get('error'),sampling_args={'temperature':config.temperature},
                    trajectory=[dict(tokens=s.get('tokens')) for s in state['trajectory']])
    finally:
        # Attempt each close even if another fails.
        cleanups=[]
        if env is not None:cleanups.append(env.teardown_rlm())
        if root is not None:cleanups.append(root.close())
        if frozen is not None:cleanups.append(frozen.close())
        results=await asyncio.gather(*cleanups,return_exceptions=True)
        if any(isinstance(r,BaseException) for r in results):raise RuntimeError('generation cleanup failed')


async def run_smoke(config,output_dir):
    output=Path(output_dir).resolve()
    if output.exists():raise FileExistsError('smoke output already exists')
    plan=prepare_smoke(config)
    output.mkdir(parents=True,exist_ok=False)
    metadata=dict(status='running',started_at=datetime.now(timezone.utc).isoformat(),
                  config=config.model_dump(mode='json'),provenance=plan.provenance)
    write_json(output/'run.json',metadata)
    result=dict(status='error',kind='not_loaded',stage=config.stage,base_model=config.base_model,
                revision=config.revision,base_quantization='nf4',objective=objective_metadata(config))
    backend=None;cancelled=None
    try:
        rollout=await collect_rollout(config,plan,output)
        # Persist only original token records; no task answer or live environment.
        safe_rollout=dict(error=None if rollout.get('error') is None else 'rollout_error',
            sampling_args=rollout.get('sampling_args'),trajectory=[dict(tokens=s.get('tokens')) for s in rollout['trajectory']])
        write_json(output/'rollout.json',safe_rollout)
        samples=samples_from_rollout(rollout,plan.prefixes,max_seq_len=config.max_seq_len)
        backend=load_backend(config,plan.snapshot,output)
        result['kind']=backend.kind
        metrics=backend.trainer.step(samples)
        if not metrics['updated']:raise ValueError('rollout contains no trainable assistant tokens')
        import torch
        ids={id(p) for p in backend.trainer.parameters}
        weights={name:p.detach().cpu() for name,p in backend.model.named_parameters() if id(p) in ids}
        checkpoint=output/'adapter.pt'
        torch.save(weights,checkpoint)
        result.update(status='completed',metrics=metrics,checkpoint=checkpoint.name,checkpoint_sha256=sha256(checkpoint))
    except (Exception,asyncio.CancelledError) as exc:
        result.update(status='error',error_type=type(exc).__name__)
        if isinstance(exc,asyncio.CancelledError):cancelled=exc
    finally:
        if backend is not None:
            try:backend.close()
            except Exception as exc:result.update(status='error',cleanup_error_type=type(exc).__name__)
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    write_json(output/'smoke.json',result)
    metadata.update(status=result['status'],finished_at=result['finished_at'])
    write_json(output/'run.json',metadata)
    if cancelled:raise cancelled
    return result
