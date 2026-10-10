"""M8 executable HTTP/CPU fixtures are explicitly not real model evaluations."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import yaml
from prime_cpu import prime_api
from test_teacher_gate import fixture_config,load_config,ROOT


def config_file(tmp_path):
    from rlm_opsd.eval.preflight import sha256
    gate_path=fixture_config(tmp_path)
    retention=tmp_path/'retention.jsonl'
    retention.write_text(json.dumps(dict(id='general-1',prompt='What is two plus two?',answer='4',answer_type='exact'))+'\n')
    adapter=tmp_path/'adapter.pt';adapter.write_bytes(b'fixture checkpoint placeholder')
    data=dict(training_config=str(ROOT/'configs/opsd.toml'),checkpoint=str(adapter),
        checkpoint_sha256=sha256(adapter),checkpoint_step=10,eval_interval=10,run_label='HTTP CPU FIXTURE',
        student_endpoint=dict(base_url='http://127.0.0.1:1/v1',served_model='fixture-student',api_key_var=None),
        endpoint_checkpoint_sha256=sha256(adapter),review_per_family=1,kl_top_k=3,temperature=1.,seed=417)
    path=tmp_path/'eval.yaml';path.write_text(yaml.safe_dump(data))
    return path,gate_path


def cfg(path):
    from rlm_opsd.eval.monitor_config import MonitorConfig
    return MonitorConfig.from_yaml(path)


@pytest.mark.parametrize('fault',['endpoint_hash','interval','checkpoint'])
def test_config_and_preflight_reject_invalid_inputs_before_inference(tmp_path,monkeypatch,fault):
    import rlm_opsd.eval.monitor as module
    path,gate_path=config_file(tmp_path);data=yaml.safe_load(path.read_text())
    if fault=='endpoint_hash':data['endpoint_checkpoint_sha256']='0'*64
    if fault=='interval':data['eval_interval']=0
    if fault=='checkpoint':data['checkpoint_sha256']=data['endpoint_checkpoint_sha256']='0'*64
    path.write_text(yaml.safe_dump(data))
    result=module.check_monitor(path)
    assert result['status']=='not_run' and not result['model_requests_sent']


def test_eval_interval_skips_without_requests_or_output(tmp_path,monkeypatch):
    import rlm_opsd.eval.monitor as module
    path,_=config_file(tmp_path);config=cfg(path).model_copy(update={'checkpoint_step':11})
    def forbidden(*args):raise AssertionError('not due should not preflight or load')
    monkeypatch.setattr(module,'prepare_monitor',forbidden)
    result=asyncio.run(module.run_monitor(config,tmp_path/'report'))
    assert result['status']=='not_due' and not (tmp_path/'report').exists()


async def http_run(tmp_path,monkeypatch,prime,*,fault=None):
    from aiohttp import web
    import rlm_opsd.eval.monitor as module
    from rlm_opsd.eval import prepare_gate
    from rlm_opsd.prompts import ChatRenderer
    from rlm_opsd.eval.preflight import sha256
    from test_training_opsd import BackboneModel
    path,gate_path=config_file(tmp_path);gate=load_config(gate_path);plan=prepare_gate(gate)
    tokenizer=ChatRenderer(plan.prompt_config).tokenizer;template=ChatRenderer(plan.prompt_config).template
    requests=[];attempt=0
    async def response(request):
        nonlocal attempt
        body=await request.json();requests.append(body)
        if fault=='http' and body['model']=='fixture-student':
            return web.json_response({'error':{'message':'PRIVATE_DO_NOT_LOG','type':'server_error'}},status=500)
        retention=body['messages'][-1]['content']=='What is two plus two?'
        text='4' if retention else 'FINAL(15)'
        if body['model']=='fixture-student' and not retention:
            attempt+=1
            if attempt%2==0:text='FINAL(0)'
        prompt=tokenizer.apply_chat_template(body['messages'],chat_template=template,
            enable_thinking=plan.prompt_config.enable_thinking,add_generation_prompt=True,tokenize=True,return_dict=False)
        ids=tokenizer.encode(text,add_special_tokens=False)
        return web.json_response(dict(id='fixture',object='chat.completion',created=0,model=body['model'],
            prompt_token_ids=prompt,choices=[dict(index=0,finish_reason='stop',message={'role':'assistant','content':text},
            token_ids=ids,logprobs={'content':[dict(token=tokenizer.decode([i]),logprob=-.1,bytes=None,top_logprobs=[]) for i in ids]})],
            usage=dict(prompt_tokens=len(prompt),completion_tokens=len(ids),total_tokens=len(prompt)+len(ids))))
    app=web.Application();app.router.add_post('/v1/chat/completions',response)
    server=web.AppRunner(app);await server.setup();site=web.TCPSite(server,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1];url=f'http://127.0.0.1:{port}/v1'
    gate=gate.model_copy(update={'root_endpoint':gate.root_endpoint.model_copy(update={'base_url':url}),
                                 'frozen_endpoint':gate.frozen_endpoint.model_copy(update={'base_url':url})})
    model=BackboneModel(prime)
    # Real small CPU backbone plus the pinned tokenizer's full vocabulary.
    model.model.embedding=torch.nn.Embedding(len(tokenizer),8);model.model.embedding.weight.requires_grad_(False)
    model.lm_head=torch.nn.Linear(8,len(tokenizer),bias=False);model.lm_head.weight.requires_grad_(False)
    adapter=tmp_path/'adapter.pt'
    torch.save({n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad},adapter)
    config=cfg(path).model_copy(update={'checkpoint_sha256':sha256(adapter),'endpoint_checkpoint_sha256':sha256(adapter),
        'student_endpoint':cfg(path).student_endpoint.model_copy(update={'base_url':url})})
    monkeypatch.setattr(module,'verify_gate',lambda _: (gate,plan))
    monkeypatch.setattr(module,'require_cuda',lambda:None)
    monkeypatch.setattr(module,'cached_snapshot',lambda _:tmp_path)
    closed=[]
    backend=SimpleNamespace(model=model,trainer=SimpleNamespace(api=prime),kind='cpu_tensor_fixture',
                            close=lambda:closed.append(True))
    monkeypatch.setattr(module,'load_backend',lambda *args:backend)
    # Avoid excessive BLAS overhead on a tiny test workload.
    old_threads=torch.get_num_threads();torch.set_num_threads(1)
    try:result=await module.run_monitor(config,tmp_path/'report')
    finally:
        torch.set_num_threads(old_threads)
        await server.cleanup()
    return result,requests,closed,config


def test_real_http_harness_scoring_and_reports(tmp_path,monkeypatch,prime_api):
    result,requests,closed,config=asyncio.run(http_run(tmp_path,monkeypatch,prime_api))
    assert result['status']=='completed',result
    assert result['kind']=='cpu_tensor_fixture' and closed==[True]
    report=tmp_path/'report'
    metrics=json.loads((report/'metrics.json').read_text())
    assert {r['phase'] for r in metrics['behavior']}=={'before','teacher','after'}
    assert 'retention' not in metrics and 'readiness' not in metrics
    assert metrics['divergence']['overall']['count']>0 and metrics['divergence']['by_category']['protocol']['count']>0
    assert (report/'behavior.csv').is_file() and (report/'divergence.csv').is_file()
    assert len(list((report/'review'/'step_10').glob('*/*.md')))==6
    assert len(list((report/'trajectories').rglob('*.json')))==18
    assert all('DO_NOT_SEND_ANSWER' not in json.dumps(r) for r in requests)
    assert all('PRIVATE_CONTEXT' not in json.dumps(r) for r in requests)
    assert not any(r['messages'][-1]['content']=='What is two plus two?' for r in requests)
    assert all(r['model'] in ('fixture-base','fixture-student') for r in requests)
    from rlm_opsd.eval.exit import load_evaluation
    with pytest.raises(ValueError,match='real|fixture'):load_evaluation(report,config.checkpoint_sha256)


def test_http_failure_preserves_partial_evidence_and_cleans_up(tmp_path,monkeypatch,prime_api):
    result,requests,closed,_=asyncio.run(http_run(tmp_path,monkeypatch,prime_api,fault='http'))
    assert result['status']=='error' and closed==[True]
    report=tmp_path/'report'
    assert (report/'monitor.json').is_file() and (report/'requests.jsonl').is_file()
    assert 'PRIVATE_DO_NOT_LOG' not in ''.join(p.read_text() for p in report.rglob('*.json*'))
    assert list((report/'trajectories').rglob('*.json'))
