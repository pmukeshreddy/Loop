"""User-selected general-capability evaluation, generated separately from behavior."""
import asyncio
import json
import math
from pathlib import Path

from .gate import GateClient,append_json
from .metrics import score_answer
from .monitor_config import RetentionItem


def load_retention(path):
    if path is None:raise ValueError('user-selected retention_path is required')
    items=[RetentionItem.model_validate(json.loads(line)).model_dump()
           for line in Path(path).read_text().splitlines()]
    if not items or len({r['id'] for r in items})!=len(items):
        raise ValueError('retention set must be nonempty with unique IDs')
    return items


async def collect_retention(config,plan,output):
    from verifiers.types import SystemMessage,UserMessage
    clients=[];rows=[]
    try:
        base=GateClient(plan.gate.root_endpoint,plan.gate.request_timeout_s,'base',output/'requests.jsonl');clients.append(base)
        student=GateClient(plan.monitor.student_endpoint,plan.gate.request_timeout_s,'student',output/'requests.jsonl');clients.append(student)
        for index,item in enumerate(plan.retention):
            row=dict(item)
            for phase,client in (('before',base),('after',student)):
                client.context=dict(task_id=item['id'],phase='retention_'+phase,seed=plan.monitor.seed+index)
                response=await client.get_response(model=client.endpoint.served_model,tools=None,
                    prompt=[SystemMessage(content='You are a helpful assistant.'),UserMessage(content=item['prompt'])],
                    sampling_args=plan.prompts.sampling_args(dict(temperature=plan.monitor.temperature,
                        seed=plan.monitor.seed+index,max_tokens=config.retention_max_tokens,top_p=1.,
                        extra_body={'top_k':-1,'min_p':0.,'repetition_penalty':1.})),state={'trajectory':[]})
                row[phase]=dict(response=response.message.model_dump(mode='json'),
                    score=score_answer(response.message.content or '',item['answer'],item['answer_type']))
                # Preserve completed responses even if the paired request later fails.
                append_json(output/'retention-responses.jsonl',dict(id=item['id'],phase=phase,**row[phase]))
            rows.append(row);append_json(output/'retention.jsonl',row)
    finally:
        results=await asyncio.gather(*(c.close() for c in clients),return_exceptions=True)
        if any(isinstance(r,BaseException) for r in results):raise RuntimeError('retention client cleanup failed')
    return {**{phase:math.fsum(r[phase]['score'] for r in rows)/len(rows) for phase in ('before','after')},'count':len(rows)}
