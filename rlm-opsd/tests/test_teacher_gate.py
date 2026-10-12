"""M5 tests use labelled fixtures only, never model-performance claims."""
import asyncio
import copy
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = dict(probe_max_chars=10,dump_threshold=25,read_threshold=15,many_hits=3,
    subcall_max_chars=40,min_batch_chars=1,max_subcalls_expected={},hand_copy_min_chars=8,dense_coverage_min=0.8)


def criterion(**overrides):
    return dict(metric='task_tag_match',dimension='overall',group='all',direction='min',threshold=0.9,
                min_known=1,max_unknown_fraction=0.0,**overrides)


def metric_row(**overrides):
    return {**dict(phase='teacher',dimension='overall',group='all',metric='task_tag_match',category='',
        value=1.0,known=2,unknown=0,trajectories=2,status='measured',trajectory_paths=['teacher.json']),**overrides}


def decide(rows, criteria=None):
    from rlm_opsd.eval import GateCriterion, evaluate_gate
    return evaluate_gate(rows,[GateCriterion(**c) for c in (criteria or [criterion()])])


def test_thresholds_are_explicit_and_operational_config_is_unset():
    from rlm_opsd.eval import GateConfig, GateCriterion
    with pytest.raises(ValueError): GateCriterion()
    with pytest.raises(ValueError): GateConfig.from_yaml(ROOT/'configs/gate.yaml')
    for overrides in ({'threshold':None},{'threshold':1.1},{'min_known':0},{'max_unknown_fraction':-1},
                      {'threshold':True},{'metric':'D19'},{'direction':'greater'},{'dimension':'checkpoint'}):
        with pytest.raises(ValueError): GateCriterion(**{**criterion(),**overrides})


def test_teacher_gate_uses_teacher_metrics_and_boundary_inclusive_comparison():
    rows = [metric_row(phase='before',value=0.0),metric_row(value=0.9)]
    result = decide(rows)
    assert result['status'] == 'passed'
    assert result['criteria'][0]['value'] == 0.9
    assert result['criteria'][0]['trajectory_paths'] == ['teacher.json']
    syntax = {**criterion(),'metric':'D16','direction':'max','threshold':0.1}
    assert decide([metric_row(metric='D16',value=0.1)],[syntax])['status'] == 'passed'
    assert decide([metric_row(metric='D16',value=0.2)],[syntax])['status'] == 'failed'


@pytest.mark.parametrize('rows', [[],[metric_row(phase='before')], [metric_row(value=None,status='no observations')],
    [metric_row(known=0,unknown=2,value=None)], [metric_row(known=1,unknown=1,status='partial')]])
def test_unknown_or_missing_evidence_does_not_pass(rows):
    assert decide(rows)['status'] == 'inconclusive'


def test_wildcard_group_checks_every_family_and_known_failures_dominate():
    criteria = [{**criterion(),'dimension':'family','group':'*'}]
    rows = [metric_row(dimension='family',group='sparse',value=1.0),
            metric_row(dimension='family',group='dense',value=0.5),
            metric_row(dimension='family',group='repo',value=None,known=0,unknown=2)]
    result = decide(rows,criteria)
    assert result['status'] == 'failed'
    assert {r['group']:r['status'] for r in result['criteria']} == {'sparse':'passed','dense':'failed','repo':'inconclusive'}
    assert decide(rows[:1]+rows[2:],criteria)['status'] == 'inconclusive'


def test_unknown_allowance_and_minimum_known_are_user_controlled():
    row=metric_row(value=1.0,known=1,unknown=1,status='partial')
    c={**criterion(),'max_unknown_fraction':0.5}
    assert decide([row],[c])['status'] == 'passed'
    c['min_known']=2
    assert decide([row],[c])['status'] == 'inconclusive'


def fixture_pool(tmp_path):
    from rlm_opsd.tasks.models import FAMILIES,Task,canonical,digest
    pool=tmp_path/'pool'; (pool/'contexts').mkdir(parents=True)
    rows=[]; grid=[]
    for i,family in enumerate(FAMILIES):
        task=Task(task_id=f'fixture-{i}',split='dev_behavior',family=family,rlm_behaviors=[family],
            behavior_rationale={family:'test fixture only'},setting='fixture',context=['PRIVATE_CONTEXT'],
            query='Return the length of the context.',answer=15,answer_type='value',answer_format='scalar',
            size_bucket=128,repo={},source='test fixture only',source_refs=[],tags=['small_context'])
        relative=f'contexts/{i}.json'
        (pool/relative).write_text(canonical(task.context))
        rows.append(task.manifest(relative))
        grid.append(dict(split='dev_behavior',family=family,size_bucket=128,count=1))
    train=copy.deepcopy(rows[0]);train.update(task_id='train-secret',split='train',answer='DO_NOT_SEND_ANSWER')
    heldout=copy.deepcopy(rows[0]);heldout.update(task_id='heldout-secret',split='eval_heldout')
    rows.extend([train,heldout])
    manifest=''.join(canonical(row)+'\n' for row in rows)
    (pool/'manifest.jsonl').write_text(manifest)
    report=dict(manifest_sha256=digest(manifest),decontamination={'coverage_complete':True},released_grid=grid)
    (pool/'build-report.json').write_text(json.dumps(report))
    return pool


def fixture_config(tmp_path, *, endpoint='http://127.0.0.1:1/v1'):
    from rlm_opsd.tasks.models import FAMILIES
    pool=fixture_pool(tmp_path)
    path=tmp_path/'detectors.yaml';path.write_text(yaml.safe_dump({**THRESHOLDS,'max_subcalls_expected':dict.fromkeys(FAMILIES,5)}))
    harness=tmp_path/'harness.yaml';harness.write_text(yaml.safe_dump(dict(max_turns=2,prefix_chars=0,max_tokens_per_turn=64,
        max_subcall_chars=40,subcall_max_tokens=16,subcall_timeout_s=2)))
    pinned=yaml.safe_load((ROOT/'configs/prompts.yaml').read_text())
    config=dict(base_model=pinned['model_name'],revision=pinned['revision'],run_label='TEST HTTP FIXTURE; NOT MODEL RESULTS',
        root_endpoint=dict(base_url=endpoint,served_model='fixture-base',api_key_var=None),
        frozen_endpoint=dict(base_url=endpoint,served_model='fixture-base',api_key_var=None),
        manifest_path=str(pool/'manifest.jsonl'),harness_config=str(harness),prompt_config=str(ROOT/'configs/prompts.yaml'),
        detector_config=str(path),temperature=0.0,seed=17,request_timeout_s=2.0,episode_timeout_s=20.0,
        criteria=[criterion()])
    cfg_path=tmp_path/'gate.yaml';cfg_path.write_text(yaml.safe_dump(config))
    return cfg_path


def load_config(path):
    from rlm_opsd.eval import GateConfig
    return GateConfig.from_yaml(path)


def test_preflight_loads_only_decontaminated_dev_inputs_with_buckets_and_no_answers(tmp_path):
    from rlm_opsd.eval import prepare_gate
    path=fixture_config(tmp_path)
    plan=prepare_gate(load_config(path))
    assert len(plan.inputs)==6
    assert {row['info']['size_bucket'] for row in plan.inputs}=={128}
    assert all('answer' not in row and 'answer' not in row['info'] for row in plan.inputs)
    assert all(row['info']['task_id'].startswith('fixture-') for row in plan.inputs)
    assert plan.provenance['manifest_sha256']
    assert plan.prompt_config.model_name=='Qwen/Qwen3.5-27B'


@pytest.mark.parametrize('fault', ['coverage','manifest','missing_grid','unknown_limits','model','empty_dev','missing_key'])
def test_preflight_rejects_invalid_inputs_before_requests(tmp_path,fault,monkeypatch):
    from rlm_opsd.eval import prepare_gate
    path=fixture_config(tmp_path)
    config=yaml.safe_load(path.read_text());pool=tmp_path/'pool'; report_path=pool/'build-report.json'
    report=json.loads(report_path.read_text())
    if fault=='coverage': report['decontamination']['coverage_complete']=False
    elif fault=='manifest': report['manifest_sha256']='0'*64
    elif fault in ('missing_grid','empty_dev'):
        from rlm_opsd.tasks.models import digest
        rows=[json.loads(line) for line in (pool/'manifest.jsonl').read_text().splitlines()]
        rows=[r for r in rows if r['split']!='dev_behavior' or (fault=='missing_grid' and r['family']!='persistent_state')]
        text=''.join(json.dumps(r)+'\n' for r in rows);(pool/'manifest.jsonl').write_text(text)
        report['manifest_sha256']=digest(text)
    elif fault=='unknown_limits':
        p=Path(config['detector_config']); values=yaml.safe_load(p.read_text());values['max_subcalls_expected']={};p.write_text(yaml.safe_dump(values))
    elif fault=='model': config['revision']='0'*40
    elif fault=='missing_key':
        config['root_endpoint']['api_key_var']='M5_MISSING_KEY';monkeypatch.delenv('M5_MISSING_KEY',raising=False)
    report_path.write_text(json.dumps(report));path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError): prepare_gate(load_config(path))


def test_config_paths_are_relative_to_config_and_urls_cannot_embed_credentials(tmp_path):
    path=fixture_config(tmp_path)
    data=yaml.safe_load(path.read_text());data['manifest_path']='pool/manifest.jsonl';path.write_text(yaml.safe_dump(data))
    assert load_config(path).manifest_path==tmp_path/'pool/manifest.jsonl'
    for url in ('http://user:secret@host/v1','https://host/v1?key=secret','file:///tmp/fake'):
        data['root_endpoint']['base_url']=url;path.write_text(yaml.safe_dump(data))
        with pytest.raises(ValueError):load_config(path)


def test_default_readiness_exposes_all_local_blockers_without_network():
    from rlm_opsd.eval import check_readiness
    result=check_readiness(ROOT/'configs/gate.yaml')
    assert result['status']=='not_run'
    reasons=' '.join(result['blockers']).lower()
    assert 'endpoint' in reasons and 'detector' in reasons and 'coverage' in reasons
    assert not result['model_requests_sent']


def response_payload(body,text,*,reasoning=None):
    message=dict(role='assistant',content=text)
    if reasoning:message['reasoning_content']=reasoning
    return dict(id='fixture-response',object='chat.completion',created=0,model=body['model'],prompt_token_ids=[1,2],
        choices=[dict(index=0,finish_reason='stop',message=message,token_ids=[91,92],
            logprobs={'content':[dict(token='a',logprob=-0.1,bytes=[97],top_logprobs=[]),dict(token='b',logprob=-0.2,bytes=[98],top_logprobs=[])]})],
        usage=dict(prompt_tokens=2,completion_tokens=2,total_tokens=4))


async def serve_fixture(tmp_path,mode='success'):
    from aiohttp import web
    requests=[]
    async def respond(request):
        body=await request.json();requests.append((request.path,body))
        if mode in ('auth_root','auth_leaf') and (mode=='auth_root' or request.path.startswith('/leaf')):
            return web.json_response({'error':{'message':'SECRET_PROVIDER_RESPONSE_DO_NOT_LOG','type':'auth_error'}},status=401)
        if mode=='http_error':return web.json_response({'error':{'message':'test failure','type':'server_error'}},status=500)
        if mode=='timeout':await asyncio.sleep(1)
        if mode=='recursive' and request.path.startswith('/leaf'):
            text='```repl\nRECURSIVE_WORKER_FAILURE = 1\n```\nFINAL(child finished)'
        elif mode=='recursive' and len(body['messages'])==2:
            text='```repl\nanswer=rlm_query("solve this task")\nprint(answer)\n```'
        elif request.path.startswith('/leaf'):
            text='15'
        elif len(body['messages'])==2:
            text='```repl\nprint(type(context),len(context))\nanswer=llm_query(context[0][:5])\nprint(answer)\n```'
        else:text='FINAL_VAR(answer)'
        payload=response_payload(body,text,reasoning='fixture reasoning')
        if mode=='wrong_model':payload['model']='different-weights'
        return web.json_response(payload)
    app=web.Application();app.router.add_post('/root/v1/chat/completions',respond);app.router.add_post('/leaf/v1/chat/completions',respond)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    path=fixture_config(tmp_path,endpoint=f'http://127.0.0.1:{port}/root/v1')
    values=yaml.safe_load(path.read_text());values['frozen_endpoint']['base_url']=f'http://127.0.0.1:{port}/leaf/v1'
    if mode=='timeout': values['episode_timeout_s']=0.1
    path.write_text(yaml.safe_dump(values))
    return runner,path,requests


def test_paired_gate_uses_real_harness_http_protocol_and_source_linked_reports(tmp_path):
    from rlm_opsd.eval import run_gate
    async def run():
        server,path,requests=await serve_fixture(tmp_path)
        output=tmp_path/'output'
        try: result=await run_gate(load_config(path),output)
        finally: await server.cleanup()
        assert result['status']=='passed'
        assert result['completed_episodes']==12 and result['planned_episodes']==12
        records=[json.loads(line) for line in (output/'records.jsonl').read_text().splitlines()]
        assert len(records)==12
        assert {r['phase'] for r in records}=={'before','teacher'}
        for r in records:
            raw=json.loads((output/r['trajectory_path']).read_text())
            assert raw['prompt_variant']==('student' if r['phase']=='before' else 'teacher')
            assert raw['size_bucket']==128 and raw['final']['value']=='15'
            assert raw['turns'][0]['assistant_token_ids']==[91,92]
            assert raw['turns'][0]['subcalls'][0]['prompt_chars']==5
            assert r['analysis']['counts']['subcall_count']==1
            assert 'task_success' not in r
        root_requests=[b for p,b in requests if p.startswith('/root')]
        leaf_requests=[b for p,b in requests if p.startswith('/leaf')]
        assert len(root_requests)==24 and len(leaf_requests)==12
        firsts=[b for b in root_requests if len(b['messages'])==2]
        assert len(firsts)==12 and all('PRIVATE_CONTEXT' not in str(b) and 'DO_NOT_SEND_ANSWER' not in str(b) for b in firsts)
        assert sum('# How to work in this REPL' in b['messages'][0]['content'] for b in firsts)==6
        for before,teacher in zip(firsts[::2],firsts[1::2]):
            assert before['messages'][1]==teacher['messages'][1]
            assert before['seed']==teacher['seed']
            assert before['chat_template_kwargs']==teacher['chat_template_kwargs']=={'enable_thinking':True}
            assert before['max_completion_tokens']==teacher['max_completion_tokens']==64
        assert all(b['messages'][2]['reasoning_content']=='fixture reasoning' for b in root_requests if len(b['messages'])>2)
        assert all(b['messages'][0]['content']=='PRIVA' for b in leaf_requests)
        report=(output/'behavior.md').read_text()
        assert 'TEST HTTP FIXTURE; NOT MODEL RESULTS' in report and 'not run' in report
        assert 'syntax_error_rate' in report and 'size_bucket' in report and 'family' in report
        assert (output/'behavior.csv').is_file() and (output/'gate.md').is_file()
        run_meta=json.loads((output/'run.json').read_text())
        assert run_meta['provenance']['revision']=='fc05daec18b0a78c049392ed2e771dde82bdf654'
        events=[json.loads(line) for line in (output/'requests.jsonl').read_text().splitlines()]
        assert len(events)==36 and all(e['response_model']=='fixture-base' for e in events)
        assert {e['role'] for e in events}=={'root','frozen'}
        assert json.loads((output/'gate.json').read_text())['status']=='passed'
        with pytest.raises(FileExistsError):await run_gate(load_config(path),output)
        assert len(requests)==36
    asyncio.run(run())


@pytest.mark.parametrize('mode',['http_error','wrong_model','timeout'])
def test_endpoint_failure_keeps_trace_and_cannot_pass_gate(tmp_path,mode):
    from rlm_opsd.eval import run_gate
    async def run():
        server,path,requests=await serve_fixture(tmp_path,mode)
        output=tmp_path/'output'
        try:result=await run_gate(load_config(path),output)
        finally:await server.cleanup()
        assert result['status']=='error'
        assert result['completed_episodes']<result['planned_episodes']
        assert result['errors']
        assert json.loads((output/'gate.json').read_text())['status']=='error'
        assert list((output/'trajectories').rglob('*.json'))
        assert (output/'behavior.md').is_file()
    asyncio.run(run())


def test_failed_preflight_creates_no_run_and_sends_no_requests(tmp_path):
    from rlm_opsd.eval import run_gate
    path=fixture_config(tmp_path)
    report=tmp_path/'pool/build-report.json';data=json.loads(report.read_text());data['decontamination']['coverage_complete']=False;report.write_text(json.dumps(data))
    with pytest.raises(ValueError):asyncio.run(run_gate(load_config(path),tmp_path/'output'))
    assert not (tmp_path/'output').exists()


def test_worker_infrastructure_error_cannot_pass_permissive_syntax_gate(tmp_path,monkeypatch):
    from rlm_opsd.eval import run_gate
    from rlm_opsd.harness.sandbox import SandboxBackend
    async def broken_execute(self,code):raise RuntimeError('worker pipe broke')
    monkeypatch.setattr(SandboxBackend,'execute',broken_execute)
    async def run():
        server,path,_=await serve_fixture(tmp_path)
        settings=yaml.safe_load(path.read_text());settings['criteria']=[{**criterion(),'metric':'D16','direction':'max','threshold':0.1}];path.write_text(yaml.safe_dump(settings))
        try:result=await run_gate(load_config(path),tmp_path/'output')
        finally:await server.cleanup()
        assert result['status']=='error'
        assert result['completed_episodes']==0 and result['errors']
    asyncio.run(run())


@pytest.mark.parametrize('fault', ['execute','setup','cleanup','budget'])
def test_recursive_worker_failures_reach_gate_but_budgets_remain_behavior(tmp_path,monkeypatch,fault):
    from rlm_opsd.eval import run_gate
    from rlm_opsd.harness.sandbox import SandboxBackend, SandboxLimit
    original_start=SandboxBackend.start
    original_execute=SandboxBackend.execute
    original_stop=SandboxBackend.stop

    async def start(self,proxy_url,rollout_id,depth=1):
        self.fixture_depth=depth
        if depth>1 and fault=='setup':raise RuntimeError('child setup failed')
        return await original_start(self,proxy_url,rollout_id,depth)

    async def execute(self,code):
        if 'RECURSIVE_WORKER_FAILURE' in code:
            if fault=='execute':raise RuntimeError('child worker pipe broke')
            if fault=='budget':raise SandboxLimit('cpu_time')
        return await original_execute(self,code)

    async def stop(self):
        await original_stop(self)
        if getattr(self,'fixture_depth',1)>1 and fault=='cleanup':
            raise RuntimeError('child cleanup failed')

    monkeypatch.setattr(SandboxBackend,'start',start)
    monkeypatch.setattr(SandboxBackend,'execute',execute)
    monkeypatch.setattr(SandboxBackend,'stop',stop)

    async def run():
        server,path,_=await serve_fixture(tmp_path,'recursive')
        settings=yaml.safe_load(path.read_text())
        settings['criteria']=[{**criterion(),'metric':'D16','direction':'max','threshold':0.1}]
        path.write_text(yaml.safe_dump(settings))
        harness=Path(settings['harness_config']);values=yaml.safe_load(harness.read_text())
        values.update(enable_recursion=True,max_depth=2,subcall_timeout_s=5)
        harness.write_text(yaml.safe_dump(values))
        output=tmp_path/'output'
        try:result=await run_gate(load_config(path),output)
        finally:await server.cleanup()
        if fault=='budget':
            assert result['status']=='passed' and not result['errors']
        else:
            assert result['status']=='error'
            assert result['completed_episodes']==0
            errors=[e for e in result['errors'] if e['task_id'].endswith('/recursive')]
            assert errors and errors[0]['stage']==fault
            child_path=output/errors[0]['trajectory_path']
            assert child_path.is_file()
            assert any(s['path']==errors[0]['trajectory_path'] for s in result['trajectories'])
    asyncio.run(run())


@pytest.mark.parametrize('mode',['auth_root','auth_leaf'])
def test_provider_auth_text_never_reaches_logs_or_the_model(tmp_path,mode):
    from rlm_opsd.eval import run_gate
    async def run():
        server,path,requests=await serve_fixture(tmp_path,mode)
        output=tmp_path/'output'
        try:result=await run_gate(load_config(path),output)
        finally:await server.cleanup()
        assert result['status']=='error'
        assert 'SECRET_PROVIDER_RESPONSE_DO_NOT_LOG' not in str(requests)
        for artifact in output.rglob('*'):
            if artifact.is_file():assert 'SECRET_PROVIDER_RESPONSE_DO_NOT_LOG' not in artifact.read_text()
        events=[json.loads(line) for line in (output/'requests.jsonl').read_text().splitlines()]
        assert any(e.get('error_type')=='AuthenticationError' for e in events)
    asyncio.run(run())


@pytest.mark.parametrize('failure',['close','analysis','constructor'])
def test_outer_failure_finalizes_error_artifacts_and_closes_both_clients(tmp_path,monkeypatch,failure):
    from rlm_opsd.eval import run_gate
    import rlm_opsd.eval.gate as module
    closed=[];original=module.GateClient.close
    async def closing(self):
        await original(self);closed.append(self.role)
        if failure=='close' and self.role=='root':raise RuntimeError('close failed')
    monkeypatch.setattr(module.GateClient,'close',closing)
    if failure=='analysis':
        def broken(*args,**kwargs):raise RuntimeError('analysis failed')
        monkeypatch.setattr(module,'analyze_trajectory',broken)
    if failure=='constructor':
        def broken(*args,**kwargs):raise RuntimeError('episode constructor failed')
        monkeypatch.setattr(module,'Episode',broken)
    async def run():
        server,path,_=await serve_fixture(tmp_path,'http_error')
        output=tmp_path/'output'
        try:result=await run_gate(load_config(path),output)
        finally:await server.cleanup()
        assert result['status']=='error'
        assert closed==['root','frozen']
        assert json.loads((output/'gate.json').read_text())['status']=='error'
        assert json.loads((output/'run.json').read_text())['status']=='error'
    asyncio.run(run())
