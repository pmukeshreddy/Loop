"""CPU validation of launch configuration and the reproducible source overlay."""
import copy
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def native_config():
    return dict(model={'name': 'Qwen/Qwen3.5-27B'}, max_steps=10, max_async_level=1,
        seq_len=8192, trainer={'opsd': {}, 'model': {'impl': 'hf', 'lora': {'rank': 16}}},
        orchestrator={'opsd': True, 'batch_size': 4, 'filters': [],
                      'train': {'env': [{'id': 'rlm_opsd.training.prime_env'}]}},
        inference={}, deployment={'num_train_gpus': 4, 'num_infer_gpus': 2})


def test_opsd_config_uses_native_async_lora_and_preserves_precision_defaults():
    from prime_rl.configs.rl import RLConfig
    from prime_rl.configs.trainer import ModelConfig
    cfg = RLConfig.model_validate(native_config())
    assert cfg.trainer.opsd is not None and cfg.orchestrator.opsd
    assert cfg.trainer.max_steps == cfg.orchestrator.max_steps == 10
    assert cfg.inference.enable_lora and cfg.inference.max_lora_rank == 16
    assert cfg.trainer.max_async_level == 1
    assert cfg.trainer.model.optimization_dtype == ModelConfig().optimization_dtype
    assert cfg.trainer.model.reduce_dtype == ModelConfig().reduce_dtype


@pytest.mark.parametrize('fault', ['no_lora', 'base_trainable', 'cp', 'compile', 'remote_teacher',
                                  'reward_filters', 'trainer_only', 'orchestrator_only', 'cpu_offload'])
def test_incompatible_native_opsd_settings_fail_configuration(fault):
    from prime_rl.configs.rl import RLConfig
    raw = native_config()
    if fault == 'no_lora': del raw['trainer']['model']['lora']
    elif fault == 'base_trainable': raw['trainer']['model']['lora']['modules_to_save'] = ['lm_head']
    elif fault == 'cp': raw['trainer']['model']['cp'] = 2
    elif fault == 'compile': raw['trainer']['model']['compile'] = {}
    elif fault == 'remote_teacher': raw['deployment']['num_teacher_gpus'] = 1
    elif fault == 'reward_filters': raw['orchestrator']['filters'] = [{'type': 'zero_advantage'}]
    elif fault == 'trainer_only': raw['orchestrator']['opsd'] = False
    elif fault == 'orchestrator_only': del raw['trainer']['opsd']
    elif fault == 'cpu_offload': raw['trainer']['model']['fsdp_cpu_offload'] = True
    with pytest.raises(ValueError): RLConfig.model_validate(raw)


def test_checked_patch_reconstructs_sources_and_rejects_drift(tmp_path):
    from rlm_opsd.training.prime_patch import apply_patch, patch_manifest
    source = ROOT / '.deps/prime-rl'
    manifest = patch_manifest()
    for relative in manifest['files']:
        payload = subprocess.check_output(['git', '-C', str(source), 'show', manifest['commit'] + ':' + relative])
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    assert apply_patch(tmp_path, verify_commit=False) == 'applied'
    assert apply_patch(tmp_path, verify_commit=False) == 'already_applied'
    for relative in manifest['files']:
        assert (tmp_path / relative).read_bytes() == (source / relative).read_bytes()
    target = tmp_path / 'src/prime_rl/trainer/rl/train.py'
    target.write_text(target.read_text() + '\n# unexpected drift\n')
    with pytest.raises(ValueError, match='modified|hash|drift'):
        apply_patch(tmp_path, verify_commit=False)


def test_shipped_configuration_parses_and_check_never_launches_gpu():
    from rlm_opsd.training.prime_launch import load_launch_config
    config, smoke = load_launch_config(ROOT / 'configs/opsd_train.toml')
    assert config.trainer.opsd and config.max_steps > 1
    assert config.trainer.model.seq_len > config.orchestrator.seq_len
    assert smoke.stage == '27b'
    assert config.orchestrator.output_dir == config.output_dir / 'run_default'
    command = subprocess.run([sys.executable, '-m', 'rlm_opsd.training.prime_launch', '--check'],
        cwd=ROOT, text=True, capture_output=True)
    assert command.returncode == 2
    assert 'not_run' in command.stdout and 'model_requests_sent' in command.stdout


def test_snapshot_preparation_survives_native_config_roundtrip(monkeypatch, tmp_path):
    from prime_rl.configs.rl import RLConfig
    from rlm_opsd.training.prime_launch import load_launch_config, prepare_config
    from rlm_opsd.training import runner
    from rlm_opsd.eval import GateConfig
    from rlm_opsd.harness.config import HarnessConfig
    import rlm_opsd.tasks.build as tasks
    from types import SimpleNamespace

    config, smoke = load_launch_config(ROOT / 'configs/opsd_train.toml')
    # External evidence and weight cache boundaries only; native configuration stays real.
    gate = SimpleNamespace(manifest_path=tmp_path / 'manifest.jsonl',
        harness_config=ROOT / 'configs/harness.yaml', request_timeout_s=300,
        frozen_endpoint=SimpleNamespace(served_model='frozen-base', base_url='http://localhost:9000/v1', api_key_var=None))
    monkeypatch.setattr(runner, 'verify_gate', lambda _: (gate, SimpleNamespace(harness_config=HarnessConfig.from_yaml(gate.harness_config))))
    monkeypatch.setattr(runner, 'verify_small_smoke', lambda _: None)
    snapshot = tmp_path / smoke.revision
    monkeypatch.setattr(runner, 'cached_snapshot', lambda _: snapshot)
    monkeypatch.setattr(tasks, 'load_tasks', lambda *a, **k: iter([{'info': {'query': 'count', 'context': 'abc'}}]))
    prepared = prepare_config(config, smoke)
    encoded = prepared.model_dump(mode='json', exclude_none=True)
    again = RLConfig.model_validate(encoded)
    assert again.trainer.model.name == again.orchestrator.model.name == again.inference.model.name == str(snapshot)
    assert again.orchestrator.output_dir == again.output_dir / 'run_default'
    assert again.orchestrator.train.env[0].args['frozen_model'] == 'frozen-base'
