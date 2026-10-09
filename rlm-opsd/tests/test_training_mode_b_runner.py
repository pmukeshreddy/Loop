"""Mode B selection and honest one-update runner evidence, without CUDA claims."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
import torch

from prime_cpu import prime_api, TinyModel, forward
from test_training_mode_b import BackboneModel
from test_training_samples import prefixes, rollout
from test_training_runner import config as mode_a_config

ROOT=Path(__file__).resolve().parents[1]


def config(stage='small'):
    from rlm_opsd.training.config import OpsdConfig
    suffix='_small' if stage=='small' else ''
    return OpsdConfig.from_toml(ROOT/f'configs/opsd_mode_b{suffix}.toml')


def test_primary_mode_b_configs_accept_gate_switch_and_reject_invalid_objectives():
    from rlm_opsd.training.config import OpsdConfig
    for stage in ('small','27b'):
        cfg=config(stage)
        assert cfg.mode=='b' and cfg.jsd_beta==.5 and not cfg.token_gate
        assert cfg.jsd_chunk_size>0
        values=cfg.model_dump();values.pop('mode')
        assert OpsdConfig.model_validate(values).mode=='b'
        gated=OpsdConfig.model_validate({**values,'token_gate':True,'token_gate_k':2.})
        assert gated.token_gate and gated.token_gate_k==2.
        for bad in ({'jsd_beta':.3},{'jsd_chunk_size':0},{'jsd_chunk_size':True},
                    {'token_gate':'yes'},{'token_gate_k':-1.},{'token_gate_k':float('nan')},
                    {'mode':'c'},{'teacher_tau':2.},{'teacher_endpoint':'https://example.org'}):
            with pytest.raises(ValueError):OpsdConfig.model_validate({**values,**bad})
    a=mode_a_config().model_dump()
    with pytest.raises(ValueError):OpsdConfig.model_validate({**a,'token_gate':True})


@pytest.mark.parametrize('mode',['a','b'])
def test_trainer_factory_selects_actual_requested_objective(prime_api,mode):
    from rlm_opsd.training.backend import create_trainer
    from test_training_samples import build
    cfg=mode_a_config() if mode=='a' else config()
    model=TinyModel(prime_api) if mode=='a' else BackboneModel(prime_api)
    trainer=create_trainer(cfg,model,api=prime_api,mode_a_forward=forward)
    if mode=='a':trainer.loss_api=prime_api.loss
    result=trainer.step(build())
    assert result['updated'] and result['assistant_tokens']==3
    assert result['gradient_norm']>0
    if mode=='b':assert 0<=result['loss']<=.693148


@pytest.mark.parametrize('fault',[None,'mode_a','legacy_missing_mode','gate','slope','beta','temperature'])
def test_mode_b_large_requires_small_mode_b_with_same_objective(tmp_path,fault):
    from rlm_opsd.training.runner import verify_small_smoke,objective_metadata
    cfg=config('27b').model_copy(update={'small_smoke_dir':tmp_path})
    small=config();checkpoint=tmp_path/'adapter.pt';checkpoint.write_bytes(b'unit proof fixture')
    record=dict(status='completed',kind='pretrained_model_smoke',stage='small',mode='b',
        base_model=small.base_model,revision=small.revision,objective=objective_metadata(small),
        metrics={'updated':True,'assistant_tokens':2},checkpoint='adapter.pt',
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    if fault=='mode_a':record['mode']='a'
    elif fault=='legacy_missing_mode':record.pop('mode')
    elif fault=='gate':record['objective']['token_gate']=True
    elif fault=='slope':record['objective']['token_gate_k']=2.
    elif fault=='beta':record['objective']['beta']=.3
    elif fault=='temperature':record['objective']['temperature']=.5
    (tmp_path/'smoke.json').write_text(json.dumps(record))
    if fault is None:verify_small_smoke(cfg)
    else:
        with pytest.raises(ValueError):verify_small_smoke(cfg)


@pytest.mark.parametrize('gate',[False,True])
def test_runner_preserves_mode_b_objective_and_runs_real_cpu_update(tmp_path,monkeypatch,prime_api,gate):
    import rlm_opsd.training.runner as module
    from rlm_opsd.training.backend import create_trainer
    cfg=config().model_copy(update={'token_gate':gate,'jsd_chunk_size':1})
    model=BackboneModel(prime_api);trainer=create_trainer(cfg,model,api=prime_api)
    plan=SimpleNamespace(prefixes=prefixes(),snapshot=tmp_path,
                         provenance={'source':'CPU FIXTURE; NOT PRETRAINED MODEL RESULTS'})
    monkeypatch.setattr(module,'prepare_smoke',lambda cfg:plan)
    closed=[]
    monkeypatch.setattr(module,'load_backend',lambda *args:SimpleNamespace(model=model,trainer=trainer,
        kind='cpu_tensor_fixture',close=lambda:closed.append(True)))
    async def collect(*args):return rollout()
    monkeypatch.setattr(module,'collect_rollout',collect)
    output=tmp_path/'run';result=asyncio.run(module.run_smoke(cfg,output))
    assert result['status']=='completed' and result['mode']=='b' and result['kind']=='cpu_tensor_fixture'
    assert result['objective']['kind']=='full_vocab_jsd' and result['objective']['token_gate']==gate
    assert result['metrics']['updated'] and 0<=result['metrics']['loss']<=.693148
    weights=torch.load(output/'adapter.pt',weights_only=True)
    assert weights and all('lora_' in name for name in weights)
    assert closed==[True]
    assert json.loads((output/'run.json').read_text())['config']['mode']=='b'


def test_mode_b_cli_default_and_make_targets_fail_closed_on_missing_prerequisites(tmp_path):
    command=[str(ROOT/'.venv/bin/python'),'-m','rlm_opsd.training','smoke','--check']
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==2 and json.loads(result.stdout)['status']=='not_run'
    # Distinguish the default B path from M6's default A small-smoke prerequisite.
    assert 'opsd-b-small' in result.stdout
    output=tmp_path/'unrun'
    result=subprocess.run(['make','opsd-b','OPSD_B_CONFIG=configs/opsd_mode_b_small.toml',
        f'OPSD_B_OUTPUT={output}'],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==2 and 'not_run' in result.stdout
    assert not output.exists()
