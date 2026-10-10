"""Actual pinned MultiLoRA/head forward, CPU only; FSDP GPU not run."""
from types import SimpleNamespace

import pytest
import torch

from prime_cpu import prime_api
from test_training_opsd import BackboneModel
from test_training_jsd import dense_reference


def micro_batch(empty=False):
    return dict(input_ids=torch.tensor([[1, 2, 3, 4]]),
                position_ids=torch.tensor([[0, 1, 2, 3]]),
                loss_mask=torch.tensor([[False, False, not empty, not empty]]),
                temperatures=torch.full((1, 4), .7),
                lora_num_tokens=torch.tensor([4], dtype=torch.int32),
                opsd_teacher_ids=[1, 7, 8, 2, 3, 4],
                opsd_prefix_lengths=[2, 4],
                opsd_teacher_positions=[] if empty else [3, 4], sft_loss=False)


def settings(gate=False):
    return SimpleNamespace(chunk_size=1, temperature=.7, token_gate=gate, gate_k=2.)


@pytest.mark.parametrize('checkpoint', [False, True])
@pytest.mark.parametrize('gate', [False, True])
def test_native_head_matches_dense_gradients_over_repeated_updates(prime_api, checkpoint, gate):
    from rlm_opsd.training.prime_step import install_opsd_head, opsd_forward
    from rlm_opsd.training.teacher import frozen_teacher
    torch.manual_seed(12)
    model = BackboneModel(prime_api, checkpoint)
    install_opsd_head(model, settings(gate))
    prime_api.lm_head._patch_model_forward(model)
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(params, lr=.1)
    initial = [p.detach().clone() for p in params]
    batch = micro_batch()
    before_teacher = None
    for step in range(3):
        # Independent dense objective; teacher first preserves student RNG.
        teacher_ids = torch.tensor([batch['opsd_teacher_ids']])
        with frozen_teacher(model, 6, api=prime_api):
            teacher = model.model(teacher_ids, torch.arange(6)[None]).last_hidden_state[0, [3, 4]]
            teacher_logits = teacher @ model.lm_head.weight.T
        if before_teacher is None:
            before_teacher = teacher_logits.clone()
        torch.testing.assert_close(teacher_logits, before_teacher, rtol=0, atol=0)
        torch.manual_seed(30 + step)
        student = model.model(batch['input_ids'], batch['position_ids']).last_hidden_state[0, [1, 2]]
        expected = dense_reference(student @ model.lm_head.weight.T, teacher_logits,
            torch.ones(2, dtype=torch.bool), temperature=.7, targets=torch.tensor([3, 4]), gate=gate, k=2.)
        expected.backward()
        gradients = [p.grad.clone() for p in params]
        optimizer.zero_grad()
        torch.manual_seed(30 + step)
        result = opsd_forward(model, batch, loss_scale=2., api=prime_api)
        torch.testing.assert_close(result['loss'], expected)
        result['loss'].backward()
        for p, grad in zip(params, gradients):
            torch.testing.assert_close(p.grad, grad, rtol=1e-4, atol=1e-7)
        assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
        optimizer.step()
        optimizer.zero_grad()
    assert any(not torch.equal(p, old) for p, old in zip(params, initial))
    assert prime_api.base.get_lora_num_tokens().tolist() == [4]
    assert prime_api.base.get_multilora_scaling().tolist() == [2.]


def test_empty_rank_keeps_forward_backward_graph(prime_api):
    from rlm_opsd.training.prime_step import install_opsd_head, opsd_forward
    model = BackboneModel(prime_api, True)
    install_opsd_head(model, settings())
    prime_api.lm_head._patch_model_forward(model)
    result = opsd_forward(model, micro_batch(empty=True), loss_scale=3., api=prime_api)
    assert result['loss'].item() == 0 and result['loss'].requires_grad
    result['loss'].backward()
    assert all(p.grad is not None and torch.count_nonzero(p.grad) == 0
               for p in model.parameters() if p.requires_grad)


def test_bad_alignment_fails_before_forward(prime_api):
    from rlm_opsd.training.prime_step import install_opsd_head, opsd_forward
    model = BackboneModel(prime_api)
    install_opsd_head(model, settings())
    batch = micro_batch()
    batch['opsd_teacher_ids'][4] = 15
    with pytest.raises(ValueError, match='align|target'):
        opsd_forward(model, batch, loss_scale=2., api=prime_api)


def test_real_fsdp_cpu_forward_backward_and_teacher_restoration(prime_api, tmp_path):
    import torch.distributed as dist
    from torch.distributed.device_mesh import init_device_mesh
    from torch.distributed.fsdp import fully_shard, MixedPrecisionPolicy
    from rlm_opsd.training.prime_step import install_opsd_head, opsd_forward
    from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import checkpoint_wrapper
    from torch import nn

    class FsdpBackbone(nn.Module):
        def __init__(self, backbone):
            super().__init__()
            self.embedding = backbone.embedding
            self.block = checkpoint_wrapper(nn.Sequential(backbone.adapter))

        def forward(self, input_ids, position_ids, **kwargs):
            x = self.embedding(input_ids).cumsum(1) / (position_ids[..., None] + 1)
            return SimpleNamespace(last_hidden_state=self.block(x))

    dist.init_process_group('gloo', init_method=(tmp_path / 'rendezvous').as_uri(), rank=0, world_size=1)
    try:
        model = BackboneModel(prime_api, True)
        model.model = FsdpBackbone(model.model)
        install_opsd_head(model, settings())
        prime_api.lm_head._patch_model_forward(model)
        mesh = init_device_mesh('cpu', (1,))
        policy = MixedPrecisionPolicy(param_dtype=torch.bfloat16, reduce_dtype=torch.float32)
        fully_shard(model.model.embedding, mesh=mesh, mp_policy=policy)
        fully_shard(model.model.block, mesh=mesh, mp_policy=policy)
        fully_shard(model.lm_head, mesh=mesh, mp_policy=policy, reshard_after_forward=False)
        fully_shard(model, mesh=mesh, mp_policy=policy)
        optimizer = torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=.1)
        for empty in (False, True, False):
            result = opsd_forward(model, micro_batch(empty=empty), loss_scale=2., api=prime_api)
            assert torch.isfinite(result['loss'])
            result['loss'].backward()
            assert all(p.grad is not None for p in model.parameters() if p.requires_grad)
            optimizer.step()
            optimizer.zero_grad()
        assert prime_api.base.get_multilora_scaling().tolist() == [2.]
    finally:
        dist.destroy_process_group()


def test_two_fsdp_cpu_ranks_match_dense_global_gradient(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    worker = Path(__file__).with_name('prime_fsdp_cpu.py')
    processes = [subprocess.Popen([sys.executable, str(worker), str(rank), str(tmp_path)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                 for rank in range(2)]
    try:
        for process in processes:
            output, _ = process.communicate(timeout=90)
            assert process.returncode == 0, output
        assert all((tmp_path / f'rank-{rank}.ok').exists() for rank in range(2))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()
