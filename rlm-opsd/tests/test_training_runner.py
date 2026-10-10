"""M6 runner contracts; CPU fixtures are never pretrained-model smoke evidence."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
import torch

from prime_cpu import prime_api, TinyModel, forward
from test_training_samples import prefixes, rollout
from test_training_opsd import BackboneModel

ROOT=Path(__file__).resolve().parents[1]


def config(stage='small'):
    from rlm_opsd.training.config import OpsdConfig
    suffix='_small' if stage=='small' else ''
    return OpsdConfig.from_toml(ROOT/f'configs/opsd{suffix}.toml')


def test_configs_require_valid_pins_and_limits():
    from rlm_opsd.training.config import OpsdConfig
    for stage in ('small','27b'):
        cfg=config(stage)
        assert cfg.stage==stage and cfg.learning_rate==2e-5
        for values in ({'revision':'0'*40},{'temperature':0},{'lora_rank':0},
                       {'teacher_endpoint':'https://example.org'},
                       {'modules_to_save':['lm_head']},{'max_steps':2},
                       {'logprobs_mode':'raw_logprobs'}):
            with pytest.raises(ValueError):OpsdConfig.model_validate({**cfg.model_dump(),**values})


def test_real_readiness_reports_unmet_gate_and_gpu_without_creating_outputs():
    from rlm_opsd.training.runner import check_readiness
    result=check_readiness(config())
    assert result['status']=='not_run' and not result['model_requests_sent']
    assert any('gate' in x.lower() for x in result['blockers'])
    # The test is about the CPU host where M6 is developed, without pretending CUDA.
    if not torch.cuda.is_available():assert any('cuda' in x.lower() for x in result['blockers'])


def test_fixture_gate_cannot_authorize_real_training():
    from rlm_opsd.training.runner import verify_gate
    cfg=config('27b').model_copy(update={'gate_dir':ROOT/'docs/logs/m5/http-fixture/report'})
    with pytest.raises(ValueError,match='fixture|synthetic'):
        verify_gate(cfg)


@pytest.mark.parametrize('fault',['missing','fixture','wrong_model','failed','missing_checkpoint','hash'])
def test_large_smoke_requires_successful_pinned_small_smoke_with_checkpoint(tmp_path,fault):
    from rlm_opsd.training.runner import verify_small_smoke
    cfg=config('27b').model_copy(update={'small_smoke_dir':tmp_path})
    checkpoint=tmp_path/'adapter.pt';checkpoint.write_bytes(b'unit-test checkpoint fixture')
    small=config()
    record=dict(status='completed',kind='pretrained_model_smoke',stage='small',
        base_model=small.base_model,revision=small.revision,
        metrics={'updated':True,'assistant_tokens':2},checkpoint='adapter.pt',
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    if fault=='fixture':record['kind']='cpu_tensor_fixture'
    elif fault=='wrong_model':record['revision']='0'*40
    elif fault=='failed':record['status']='error'
    elif fault=='missing_checkpoint':checkpoint.unlink()
    elif fault=='hash':record['checkpoint_sha256']='0'*64
    if fault!='missing':(tmp_path/'smoke.json').write_text(json.dumps(record))
    with pytest.raises((ValueError,OSError)):verify_small_smoke(cfg)


@pytest.mark.parametrize('fault',[None,'missing_tokens','forward','cleanup'])
def test_smoke_runner_runs_real_cpu_step_and_saves_honest_evidence(tmp_path,monkeypatch,prime_api,fault):
    import rlm_opsd.training.runner as module
    from rlm_opsd.training.opsd import OpsdTrainer, backbone_hidden
    cfg=config();model=BackboneModel(prime_api);closed=[]
    def broken(*args,**kwargs):raise RuntimeError('injected model failure')
    trainer=OpsdTrainer(model,hidden_fn=broken if fault=='forward' else backbone_hidden,
                        api=prime_api,learning_rate=0.01)
    def close():
        closed.append(True)
        if fault=='cleanup':raise RuntimeError('injected cleanup failure')
    backend=SimpleNamespace(trainer=trainer,model=model,kind='cpu_tensor_fixture',close=close)
    plan=SimpleNamespace(prefixes=prefixes(),task={'info':{'task_id':'unit','family':'small_context_control'}},
                         provenance={'source':'TEST CPU FIXTURE; NOT MODEL RESULTS'},snapshot=tmp_path)
    monkeypatch.setattr(module,'prepare_smoke',lambda config:plan)
    monkeypatch.setattr(module,'load_backend',lambda *args:backend)
    async def collect(*args):
        value=rollout()
        if fault=='missing_tokens':value['trajectory'][0]['tokens']=None
        return value
    monkeypatch.setattr(module,'collect_rollout',collect)
    output=tmp_path/'run'
    result=asyncio.run(module.run_smoke(cfg,output))
    assert result['kind']=='cpu_tensor_fixture' if fault!='missing_tokens' else result['status']=='error'
    assert result['status']==('completed' if fault is None else 'error')
    assert json.loads((output/'smoke.json').read_text())['status']==result['status']
    assert json.loads((output/'run.json').read_text())['status']==result['status']
    if fault!='missing_tokens':assert closed==[True]
    if fault is None:
        assert result['metrics']['updated'] and result['metrics']['assistant_tokens']==3
        weights=torch.load(output/result['checkpoint'],weights_only=True)
        assert weights and all('lora_' in key for key in weights)
        assert 'NEVER_COPY' not in (output/'rollout.json').read_text()
    with pytest.raises(FileExistsError):asyncio.run(module.run_smoke(cfg,output))


def test_cli_and_make_reject_unready_real_run_without_output(tmp_path):
    output=tmp_path/'unrun'
    result=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','rlm_opsd.training','smoke',
        '--config',str(ROOT/'configs/opsd_small.toml'),'--output',str(output)],
        cwd=ROOT,text=True,capture_output=True)
    assert result.returncode==2 and json.loads(result.stdout)['status']=='not_run'
    assert not output.exists()
    command=subprocess.run(['make','-n','opsd'],cwd=ROOT,text=True,capture_output=True)
    assert command.returncode==0 and 'rlm_opsd.training smoke' in command.stdout


def test_cached_snapshot_accepts_huggingface_blob_symlinks_but_not_index_traversal(tmp_path,monkeypatch):
    from rlm_opsd.training.runner import cached_snapshot
    import huggingface_hub
    cfg=config()
    root=tmp_path/'hub';snapshot=root/'snapshots'/cfg.revision;snapshot.mkdir(parents=True)
    blobs=root/'blobs';blobs.mkdir();(blobs/'weights').write_bytes(b'unit cache layout fixture')
    (snapshot/'model.safetensors').symlink_to(blobs/'weights')
    def cached(name,*,revision,local_files_only):
        assert name==cfg.base_model and revision==cfg.revision and local_files_only
        return str(snapshot)
    monkeypatch.setattr(huggingface_hub,'snapshot_download',cached)
    assert cached_snapshot(cfg)==snapshot
    (snapshot/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'p':'../escape.safetensors'}}))
    with pytest.raises(ValueError):cached_snapshot(cfg)


def test_backend_adapter_setup_uses_portable_matmul_and_requires_initial_base(prime_api):
    from rlm_opsd.training.backend import configure_adapters
    model=TinyModel(prime_api)
    with pytest.raises(ValueError,match='zero'):
        configure_adapters(model,rank=2,alpha=4.0,api=prime_api)
    with torch.no_grad():model.projection.lora_B[0].zero_()
    model.projection.use_grouped_mm=True
    configure_adapters(model,rank=2,alpha=4.0,api=prime_api)
    ids=torch.tensor([[1,2,3,4]]);pos=torch.arange(4)[None,:]
    # CPU cannot use the CUDA grouped path; real upstream fallback must work.
    actual=forward(model,ids,pos)['logits']
    expected=model.projection.base_layer(model.features(ids,pos))
    torch.testing.assert_close(actual,expected,rtol=0,atol=0)


def test_rollout_sampling_matches_unrestricted_temperature_scaled_policy(tmp_path,monkeypatch):
    import rlm_opsd.training.runner as module
    import rlm_opsd.harness
    cfg=config();captured={};closed=[]
    endpoint=SimpleNamespace(served_model='base')
    class Client:
        def __init__(self,endpoint,timeout,role,path):self.errors=[];self.role=role
        async def close(self):closed.append(self.role)
    class Env:
        def __init__(self,**kwargs):pass
        async def rollout(self,**kwargs):
            captured.update(kwargs['sampling_args'])
            return {**rollout(),'opsd_episode':SimpleNamespace(infrastructure_errors=[])}
        async def teardown_rlm(self):closed.append('env')
    monkeypatch.setattr(module,'GateClient',Client)
    monkeypatch.setattr(rlm_opsd.harness,'RLMOpsdEnv',Env)
    plan=SimpleNamespace(task={'info':{'task_id':'unit','query':'query'}},
        gate_plan=SimpleNamespace(harness_config=None),gate_config=SimpleNamespace(
            root_endpoint=endpoint,frozen_endpoint=endpoint,request_timeout_s=10,episode_timeout_s=10))
    result=asyncio.run(module.collect_rollout(cfg,plan,tmp_path))
    assert captured['temperature']==cfg.temperature
    assert captured.get('top_p')==1.0
    assert captured.get('presence_penalty')==captured.get('frequency_penalty')==0.0
    assert captured['extra_body'].get('top_k')==-1
    assert captured['extra_body'].get('min_p')==0.0
    assert captured['extra_body'].get('repetition_penalty')==1.0
    assert captured['extra_body']['return_token_ids'] and captured['logprobs']
    assert cfg.logprobs_mode=='processed_logprobs'
    assert result['trajectory']==rollout()['trajectory'] and sorted(closed)==['env','frozen','root']


@pytest.mark.parametrize('fault',[None,'variant','family','domain','tags','size_bucket','request_role'])
def test_gate_evidence_must_match_phase_and_current_task_metadata(tmp_path,fault):
    """Exercise validation with copied fixture traces, never authorize a model run."""
    import shutil
    from rlm_opsd.training.runner import verify_gate
    root=ROOT/'docs/logs/m5/http-fixture'
    report=tmp_path/'report';shutil.copytree(root/'report',report)
    gate=json.loads((report/'gate.json').read_text())
    # Fixture-label rejection is tested separately; exercise the subsequent checks.
    gate['run_label']='UNIT CONTRACT TEST'
    (report/'gate.json').write_text(json.dumps(gate))
    source=next(s for s in gate['trajectories'] if s['phase']=='teacher')
    path=report/source['path'];raw=json.loads(path.read_text())
    if fault=='variant':raw['prompt_variant']='student'
    elif fault in ('family','domain'):raw[fault]='different'
    elif fault=='tags':raw['tags']=[]
    elif fault=='size_bucket':raw['size_bucket']=999
    path.write_text(json.dumps(raw))
    if fault=='request_role':
        requests=report/'requests.jsonl'
        rows=[json.loads(line) for line in requests.read_text().splitlines()]
        next(r for r in rows if r['role']=='frozen')['role']='unknown'
        requests.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    cfg=config('27b').model_copy(update={'gate_dir':report,'gate_config':root/'inputs/gate.yaml'})
    if fault is None:
        _,plan=verify_gate(cfg)
        assert len(plan.inputs)==6
    else:
        with pytest.raises(ValueError):verify_gate(cfg)
