"""Real NF4 storage, BF16 computation, adapter updates and checkpoint reload."""
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from transformers import LlamaConfig, LlamaForCausalLM

from prime_cpu import prime_api, prime_checkpoint
from test_training_samples import build


@pytest.fixture
def nf4_model(tmp_path):
    from rlm_opsd.training.qlora import load_nf4_weights
    torch.manual_seed(19)
    config = LlamaConfig(vocab_size=16, hidden_size=32, intermediate_size=64,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
        head_dim=8, use_cache=False, tie_word_embeddings=False)
    config._attn_implementation = 'eager'
    LlamaForCausalLM(config).save_pretrained(tmp_path)
    with torch.device('meta'):
        skeleton = LlamaForCausalLM(config)
    source = SimpleNamespace(name=str(tmp_path), trust_remote_code=False)
    return load_nf4_weights(skeleton, source, torch.device('cpu'))


def attach_adapter(model, api):
    # Match MultiRunManager's production routing dtype.
    api.base.set_multilora_scaling(torch.tensor([2.], dtype=torch.bfloat16), reset_reference=True)
    attention = model.model.layers[0].self_attn
    attention.q_proj = api.MultiLoRALinear(attention.q_proj, rank=2, n_adapters=1,
        alpha=4, dropout=0., use_grouped_mm=False)
    return attention.q_proj


def test_nf4_storage_bf16_step_frozen_teacher_and_adapter_reload(nf4_model, prime_api, tmp_path):
    from bitsandbytes.functional import dequantize_4bit
    from rlm_opsd.training.qlora import NF4Linear
    from rlm_opsd.training.opsd import OpsdTrainer, backbone_hidden
    from rlm_opsd.training.teacher import frozen_teacher
    model = nf4_model
    layers = [m for m in model.modules() if isinstance(m, NF4Linear)]
    assert len(layers) == 14  # attention + MLP, including non-adapted layers
    for layer in layers:
        assert type(layer.weight) is nn.Parameter and not layer.weight.requires_grad
        assert layer.weight.dtype == torch.bfloat16
        assert layer.weight.numel() * 4 == layer.in_features * layer.out_features
        assert layer.quant_state.quant_type == 'nf4' and layer.quant_state.nested
        x = torch.randn(3, layer.in_features, dtype=torch.bfloat16, requires_grad=True)
        expected_weight = dequantize_4bit(layer.weight, layer.quant_state)
        actual = layer(x)
        assert actual.dtype == torch.bfloat16
        torch.testing.assert_close(actual, nn.functional.linear(x, expected_weight))
        actual.sum().backward()
        torch.testing.assert_close(x.grad, torch.ones_like(actual) @ expected_weight)
    adapter = attach_adapter(model, prime_api)
    model.train()
    frozen = {n: p.detach().view(torch.uint8).clone() for n, p in model.named_parameters() if not p.requires_grad}
    sample = build()[0]
    ids = torch.tensor([sample.teacher_ids])
    positions = torch.arange(ids.shape[1])[None]
    with frozen_teacher(model, ids.shape[1], api=prime_api):
        teacher = backbone_hidden(model, ids, positions).clone()
    result = OpsdTrainer(model, api=prime_api, chunk_size=1, learning_rate=.01).step([sample])
    assert result['updated'] and result['gradient_norm'] > 0 and 0 < result['loss'] < .694
    assert torch.count_nonzero(adapter.lora_B[0]) > 0
    for name, param in model.named_parameters():
        if name in frozen:
            assert param.grad is None
            assert torch.equal(param.detach().view(torch.uint8), frozen[name])
    with frozen_teacher(model, ids.shape[1], api=prime_api):
        torch.testing.assert_close(backbone_hidden(model, ids, positions), teacher, rtol=0, atol=0)
    prime_api.base.set_lora_num_tokens(torch.tensor([ids.shape[1]], dtype=torch.int32))
    expected = backbone_hidden(model, ids, positions).detach()
    checkpoint = tmp_path / 'adapter.pt'
    torch.save({n: p.detach() for n, p in model.named_parameters() if p.requires_grad}, checkpoint)
    with torch.no_grad():
        for p in [*adapter.lora_A, *adapter.lora_B]:
            p.zero_()
    weights = torch.load(checkpoint, weights_only=True)
    assert weights and all('lora_' in name for name in weights)
    model.load_state_dict(weights, strict=False)
    torch.testing.assert_close(backbone_hidden(model, ids, positions), expected, rtol=0, atol=0)


@pytest.mark.parametrize('checkpoint', [False, True])
def test_nf4_two_rank_fsdp_training_and_checkpoint_resume(nf4_model, tmp_path, checkpoint):
    import subprocess
    import sys
    from pathlib import Path
    worker = Path(__file__).with_name('qlora_fsdp_cpu.py')
    processes = [subprocess.Popen([sys.executable, str(worker), str(rank), str(tmp_path), str(int(checkpoint))],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for rank in range(2)]
    try:
        for process in processes:
            output, _ = process.communicate(timeout=120)
            assert process.returncode == 0, output
        assert all((tmp_path / f'qlora-rank-{rank}.ok').exists() for rank in range(2))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()


def test_native_weight_checkpoint_exports_reloadable_adapter(nf4_model, prime_api, prime_checkpoint, tmp_path, monkeypatch):
    import json
    from safetensors.torch import load_file
    from prime_rl.configs.trainer import LoRAConfig, WeightCheckpointConfig
    from prime_rl.trainer.runs import MultiRunManager
    from rlm_opsd.training.opsd import OpsdTrainer, backbone_hidden
    model = nf4_model
    adapter = attach_adapter(model, prime_api)
    model.train()
    OpsdTrainer(model, api=prime_api, learning_rate=.01).step([build()[0]])
    # Real native adapter key conversion; manager discovery needs a live orchestrator.
    manager = object.__new__(MultiRunManager)
    manager._modules = [('model.layers.0.self_attn.q_proj', adapter)]
    manager._adapter_state_dict_converter = None
    monkeypatch.setattr(prime_checkpoint, 'get_multi_run_manager', lambda: manager)
    checkpoint = prime_checkpoint.WeightCheckpointManager(tmp_path / 'output', WeightCheckpointConfig(),
        lora_config=LoRAConfig(rank=2, alpha=4, target_modules=['q_proj']))
    checkpoint.save(1, model, tokenizer=None)
    path = checkpoint.get_step_path(1)
    assert (path / 'STABLE').exists()
    weights = load_file(path / 'adapter_model.safetensors')
    assert set(weights) == {'base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight',
                            'base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight'}
    assert json.loads((path / 'adapter_config.json').read_text())['base_model_name_or_path'] == str(tmp_path)
    assert not (path / 'model.safetensors').exists()
    ids = torch.tensor([[1, 2, 3, 4]])
    positions = torch.arange(4)[None]
    expected = backbone_hidden(model, ids, positions).detach()
    with torch.no_grad():
        for name in ('lora_A', 'lora_B'):
            getattr(adapter, name)[0].zero_()
            getattr(adapter, name)[0].copy_(weights[f'base_model.model.model.layers.0.self_attn.q_proj.{name}.weight'])
    torch.testing.assert_close(backbone_hidden(model, ids, positions), expected, rtol=0, atol=0)
