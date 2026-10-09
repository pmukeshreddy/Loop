"""Paired baseline/teacher endpoint rollouts using the persistent RLM harness."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote

from verifiers.clients import OpenAIChatCompletionsClient
from verifiers.types import ClientConfig
from verifiers.utils.message_utils import normalize_messages

from rlm_opsd.detectors import analyze_trajectory, aggregate_behavior, write_behavior_report
from rlm_opsd.harness.episode import Episode
from .decision import evaluate_gate
from .preflight import prepare_gate


def write_json(path,value):
    path=Path(path)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    temporary.replace(path)


def append_json(path,value):
    with Path(path).open('a') as handle:
        handle.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')


class EndpointRequestError(RuntimeError):
    """Safe exception text for the harness observation/trajectory boundary."""


class GateClient(OpenAIChatCompletionsClient):
    """Pinned client plus endpoint identity checks and request provenance."""
    def __init__(self,endpoint,timeout,role,event_path):
        super().__init__(ClientConfig(api_base_url=endpoint.base_url,
            api_key_var=endpoint.api_key_var or '',timeout=timeout,connect_timeout=min(timeout,5.0),
            max_retries=0,max_connections=64,max_keepalive_connections=16))
        self.endpoint,self.role,self.event_path=endpoint,role,event_path
        self.context={}
        self.errors=[]

    async def get_response(self,**request):
        start=time.monotonic()
        event={**self.context,'role':self.role,'requested_model':request['model']}
        try:
            response=await super().get_response(**request)
            if response.model != self.endpoint.served_model:
                raise ValueError('endpoint response model does not match served_model')
            event.update(status='completed',response_id=response.id,response_model=response.model,
                         token_ids_available=response.message.tokens is not None,
                         usage=response.usage.model_dump() if response.usage else None)
            return response
        except (Exception,asyncio.CancelledError) as exc:
            # Do not persist provider exception text, headers or credentials.
            event.update(status='error',error_type=type(exc).__name__)
            self.errors.append(dict(event))
            if isinstance(exc,asyncio.CancelledError):
                raise
            raise EndpointRequestError(f'endpoint request failed: {type(exc).__name__}') from None
        finally:
            event['latency_s']=time.monotonic()-start
            append_json(self.event_path,event)


def gate_markdown(result,label):
    lines=['# Teacher gate','',label,'',f"Status: **{result['status']}**",'',
           '[Behavior report](behavior.md) · [CSV](behavior.csv) · [Run provenance](run.json) · [Requests](requests.jsonl)',
           '',f"Completed episodes: {result['completed_episodes']} / {result['planned_episodes']}",
           '', 'Thresholds apply to teacher-as-policy evidence. Baseline metrics remain in the behavior report.',
           '', '| Metric | Dimension / group | Rule | Value | Known / unknown | Status |',
           '| --- | --- | --- | ---: | ---: | --- |']
    for row in result['criteria']:
        value='unknown' if row['value'] is None else str(row['value'])
        lines.append(f"| {row['metric']} | {row['dimension']} / {row['group']} | {row['direction']} {row['threshold']} | {value} | {row['known']} / {row['unknown']} | {row['status']} |")
    if result['errors']:
        lines+=['','Run errors (exception types only; see preserved trajectories and requests):','']
        for error in result['errors']:
            lines.append(f"- {error['phase']} / {error['task_id']}: {error['error_type']}")
    lines+=['','Source trajectories:','']
    for item in result['trajectories']:
        lines.append(f"- {item['phase']}: [{item['task_id']}]({quote(item['path'],safe='/')})")
    lines+=['','After/checkpoint phase: not run. Task success is not scored by this gate.',
            'Endpoint weights/template identity is operator-declared; response model aliases are checked.']
    return '\n'.join(lines)+'\n'


async def run_gate(config,output_dir):
    """Run every fixed dev task under x and y*, preserving partial failures.

    Preflight errors raise before output creation or network activity. Existing
    outputs are never replaced. Infrastructure failures return status=error;
    model behavior (including budgets/invalid finishes) stays measured evidence.
    """
    output=Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError('gate output already exists; choose a new run directory')
    plan=prepare_gate(config)
    output.mkdir(parents=True,exist_ok=False)
    settings=config.model_dump(mode='json')
    run_meta=dict(started_at=datetime.now(timezone.utc).isoformat(),status='running',
                  config=settings,config_sha256=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest(),
                  provenance=plan.provenance)
    write_json(output/'run.json',run_meta)
    (output/'requests.jsonl').touch()
    (output/'records.jsonl').touch()
    clients=[];records=[];errors=[];sources=[];completed=0;cancelled=None
    try:
        root=GateClient(config.root_endpoint,config.request_timeout_s,'root',output/'requests.jsonl');clients.append(root)
        frozen=GateClient(config.frozen_endpoint,config.request_timeout_s,'frozen',output/'requests.jsonl');clients.append(frozen)
        stop=False
        for task_index,example in enumerate(plan.inputs):
            if stop:break
            for phase,variant in (('before','student'),('teacher','teacher')):
                info=example['info']
                episode=Episode(config=plan.harness_config,info=info,frozen_client=frozen,
                    frozen_model=config.frozen_endpoint.served_model,log_dir=output/'trajectories'/phase,
                    prompt_builder=plan.prompt_builder,prompt_config=plan.prompt_config,prompt_variant=variant)
                context=dict(task_id=info['task_id'],phase=phase,trajectory_path=str(episode.log_path.relative_to(output)))
                root.context=frozen.context=context
                error_count=len(frozen.errors)
                try:
                    async with asyncio.timeout(config.episode_timeout_s):
                        async with episode:
                            while not episode.done:
                                response=await root.get_response(prompt=normalize_messages(episode.messages),
                                    model=config.root_endpoint.served_model,tools=None,
                                    sampling_args=plan.prompt_config.sampling_args(dict(
                                        max_tokens=plan.harness_config.max_tokens_per_turn,
                                        temperature=config.temperature,seed=config.seed+task_index)),state={'trajectory':[]})
                                message=response.message
                                tokens=message.tokens.completion_ids if message.tokens else []
                                await episode.accept(message.content or '',tokens)
                                episode.messages[-2]=message.model_dump(exclude_none=True)
                    if len(frozen.errors)>error_count:
                        raise RuntimeError('frozen endpoint request failed')
                    if episode.infrastructure_errors:
                        raise RuntimeError('harness worker failure')
                    completed+=1
                except (Exception,asyncio.CancelledError) as exc:
                    await episode.close(error=type(exc).__name__)
                    errors.append(dict(phase=phase,task_id=info['task_id'],error_type=type(exc).__name__))
                    stop=True
                    if isinstance(exc,asyncio.CancelledError):cancelled=exc
                for failure in episode.infrastructure_errors:
                    relative=str(Path(failure['trajectory_path']).relative_to(output))
                    errors.append({**failure,'phase':phase,'trajectory_path':relative})
                    if (Path(failure['trajectory_path']).is_file() and relative!=context['trajectory_path']
                            and not any(source['path']==relative for source in sources)):
                        sources.append(dict(phase=phase,task_id=failure['task_id'],path=relative))
                # Even failed episodes retain their available measured evidence.
                if episode.log_path.is_file():
                    relative=str(episode.log_path.relative_to(output))
                    sources.append(dict(phase=phase,task_id=info['task_id'],path=relative))
                    trajectory=json.loads(episode.log_path.read_text())
                    analysis=analyze_trajectory(trajectory,plan.detector_config)
                    record=dict(phase=phase,trajectory_path=str(episode.log_path),analysis=analysis)
                    records.append(record)
                    append_json(output/'records.jsonl',{**record,'trajectory_path':relative})
                if stop:break
    except (Exception,asyncio.CancelledError) as exc:
        errors.append(dict(phase='run',task_id='run',error_type=type(exc).__name__))
        if isinstance(exc,asyncio.CancelledError):cancelled=exc
    finally:
        for client in clients:
            try:
                await client.close()
            except (Exception,asyncio.CancelledError) as exc:
                errors.append(dict(phase='cleanup',task_id=client.role,error_type=type(exc).__name__))
                if isinstance(exc,asyncio.CancelledError):cancelled=exc
    try:
        write_behavior_report(records,output,source_label=config.run_label)
        decision=evaluate_gate(aggregate_behavior(records),config.criteria)
    except Exception as exc:
        errors.append(dict(phase='report',task_id='run',error_type=type(exc).__name__))
        decision=dict(status='error',criteria=[])
    result={**decision,'planned_episodes':2*len(plan.inputs),'completed_episodes':completed,
            'errors':errors,'trajectories':sources,'run_label':config.run_label}
    if errors or completed!=result['planned_episodes']:
        result['status']='error'
    write_json(output/'gate.json',result)
    (output/'gate.md').write_text(gate_markdown(result,config.run_label))
    run_meta.update(status=result['status'],finished_at=datetime.now(timezone.utc).isoformat())
    write_json(output/'run.json',run_meta)
    if cancelled:raise cancelled
    return result
