"""Exit retention uses real HTTP clients, with explicitly scripted fixture replies."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_exit_check import evidence,settings
from test_teacher_gate import fixture_config,load_config,response_payload
from test_monitor_runner import config_file,cfg


@pytest.mark.parametrize('fault',['unset','duplicate','schema','empty'])
def test_required_retention_input_cannot_be_missing_or_ambiguous(tmp_path,fault):
    from rlm_opsd.eval.retention import load_retention
    path=tmp_path/'retention.jsonl'
    item=dict(id='one',prompt='Question',answer='Answer',answer_type='exact')
    if fault=='unset':path=None
    elif fault=='duplicate':path.write_text((json.dumps(item)+'\n')*2)
    elif fault=='schema':path.write_text('{"id":"one"}\n')
    else:path.write_text('')
    with pytest.raises((ValueError,TypeError)):load_retention(path)


async def run_fixture(tmp_path,monkeypatch,fault):
    from aiohttp import web
    from rlm_opsd.eval.monitor_config import ExitConfig
    from rlm_opsd.eval import exit as module
    from rlm_opsd.prompts import PromptConfig
    config_path,gate_path=config_file(tmp_path)
    monitor=cfg(config_path);gate=load_config(gate_path)
    source=tmp_path/'evaluation';source.mkdir();(source/'monitor.json').write_text('{}')
    data=tmp_path/'retention.jsonl'
    items=[dict(id='one',prompt='Name two letters',answer=['a','b'],answer_type='list_f1')]
    data.write_text(json.dumps(items[0])+'\n')
    requests=[]
    async def response(request):
        body=await request.json();requests.append(body)
        if fault=='http':return web.json_response({'error':{'message':'PRIVATE_RESPONSE_SECRET','type':'server_error'}},status=500)
        text='["a", "b"]' if body['model']=='fixture-base' else '["a", "c"]'
        return web.json_response(response_payload(body,text))
    app=web.Application();app.router.add_post('/v1/chat/completions',response)
    server=web.AppRunner(app);await server.setup();site=web.TCPSite(server,'127.0.0.1',0);await site.start()
    url=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/v1'
    gate=gate.model_copy(update={'root_endpoint':gate.root_endpoint.model_copy(update={'base_url':url})})
    monitor=monitor.model_copy(update={'student_endpoint':monitor.student_endpoint.model_copy(update={'base_url':url})})
    plan=SimpleNamespace(metrics={'behavior':evidence()['behavior']},monitor=monitor,gate=gate,
        prompts=PromptConfig.from_yaml(),retention=items)
    monkeypatch.setattr(module,'prepare_exit',lambda _:plan)
    config=ExitConfig(evaluation_dir=source,expected_checkpoint_sha256='1'*64,retention_path=data,
        retention_max_tokens=32,rules=settings(retention_tolerance=.5))
    try:result=await module.run_exit(config,tmp_path/'exit')
    finally:await server.cleanup()
    return result,requests,config


@pytest.mark.parametrize('fault',[None,'http'])
def test_exit_runs_paired_retention_and_never_accepts_request_errors(tmp_path,monkeypatch,fault):
    result,requests,config=asyncio.run(run_fixture(tmp_path,monkeypatch,fault))
    assert result['status']==('error' if fault else 'passed'),result
    if not fault:
        assert result['retention']['drop']==.5
        assert result['retention_scores']=={'before':1.,'after':.5,'count':1}
        assert [r['model'] for r in requests]==['fixture-base','fixture-student']
        assert requests[0]['seed']==requests[1]['seed']
        assert all(r['messages'][-1]['content']=='Name two letters' for r in requests)
        # Pinned verifiers maps max_tokens to the provider's completion key.
        assert all(r['max_completion_tokens']==32 for r in requests)
    output=tmp_path/'exit'
    assert (output/'exit.json').is_file() and (output/'requests.jsonl').is_file()
    assert 'PRIVATE_RESPONSE_SECRET' not in ''.join(p.read_text() for p in output.glob('*.json*'))
    assert '../evaluation/monitor.json' in (output/'exit.md').read_text()


def test_exit_preflight_accepts_behavior_provenance_and_rejects_changed_inputs(tmp_path,monkeypatch):
    from rlm_opsd.eval import exit as module,prepare_gate
    from rlm_opsd.eval.preflight import sha256
    from rlm_opsd.eval.monitor_config import ExitConfig
    from rlm_opsd.eval.gate import write_json
    path,gate_path=config_file(tmp_path);monitor=cfg(path);gate=load_config(gate_path);plan=prepare_gate(gate)
    source=tmp_path/'evaluation';source.mkdir()
    provenance={**plan.provenance,'training_config_sha256':sha256(monitor.training_config),
                'endpoint_identity':'operator-declared base/checkpoint/template identity; response aliases checked'}
    write_json(source/'run.json',dict(config=monitor.model_dump(mode='json'),provenance=provenance))
    monkeypatch.setattr(module,'load_evaluation',lambda *args:{'behavior':evidence()['behavior']})
    import rlm_opsd.training.runner as training
    monkeypatch.setattr(training,'verify_gate',lambda _: (gate,plan))
    config=ExitConfig(evaluation_dir=source,expected_checkpoint_sha256=monitor.checkpoint_sha256,
        retention_path=tmp_path/'retention.jsonl',rules=settings())
    prepared=module.prepare_exit(config)
    assert len(prepared.retention)==1 and prepared.monitor.student_endpoint==monitor.student_endpoint
    provenance['manifest_sha256']='0'*64
    write_json(source/'run.json',dict(config=monitor.model_dump(mode='json'),provenance=provenance))
    with pytest.raises(ValueError,match='changed'):module.prepare_exit(config)


@pytest.mark.parametrize('kind,answer', [
    ('numeric','not-a-number'),('numeric','NaN'),('numeric',float('inf')),('numeric',[4]),
    ('list_f1','not a list'),('list_f1','{"a": 1}'),('list_f1','[NaN]'),
    ('list_f1',[float('nan')]),('exact',['a']),
])
def test_invalid_gold_is_rejected_before_it_can_make_both_models_score_zero(tmp_path,kind,answer):
    from rlm_opsd.eval.retention import load_retention
    path=tmp_path/'bad-gold.jsonl'
    path.write_text(json.dumps(dict(id='one',prompt='Question',answer=answer,answer_type=kind))+'\n')
    with pytest.raises(ValueError):load_retention(path)
