"""Two real CPU/Gloo FSDP ranks compared with an independent dense objective."""
from pathlib import Path
import sys

import pytest
import torch
from torch import nn
import torch.distributed as dist
from torch.distributed.device_mesh import init_device_mesh
from torch.distributed.fsdp import fully_shard
from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import checkpoint_wrapper

from prime_cpu import prime_api
from test_prime_opsd_step import micro_batch, settings
from test_training_opsd import BackboneModel
from test_training_jsd import dense_reference
from rlm_opsd.training.prime_step import install_opsd_head, opsd_forward, global_loss_scale
from rlm_opsd.training.teacher import frozen_teacher


class ShardedBackbone(nn.Module):
    def __init__(self, backbone):
        super().__init__()
        self.embedding = backbone.embedding
        self.block = checkpoint_wrapper(nn.Sequential(backbone.adapter))

    def forward(self, input_ids, position_ids, **kwargs):
        from types import SimpleNamespace
        x = self.embedding(input_ids).cumsum(1) / (position_ids[..., None] + 1)
        return SimpleNamespace(last_hidden_state=self.block(x))


def batch_for(rank, step):
    batch = micro_batch(empty=rank == 1 and step == 1)
    if rank == 1 and step != 1:
        batch['loss_mask'][0, 3] = False
        batch['opsd_teacher_positions'] = [3]
    return batch


def dense_loss(model, api, batch):
    targets_at = batch['loss_mask'][0].nonzero().flatten()
    teacher_ids = torch.tensor([batch['opsd_teacher_ids']])
    with frozen_teacher(model, 6, api=api):
        teacher = model.model(teacher_ids, torch.arange(6)[None]).last_hidden_state
        teacher = teacher[0, batch['opsd_teacher_positions']] @ model.lm_head.weight.T
    student = model.model(batch['input_ids'], batch['position_ids']).last_hidden_state
    student = student[0, targets_at - 1] @ model.lm_head.weight.T
    return dense_reference(student, teacher, torch.ones(len(targets_at), dtype=torch.bool),
        temperature=.7, targets=batch['input_ids'][0, targets_at], gate=False, k=2.)


def run(rank, folder):
    torch.set_num_threads(1)
    with pytest.MonkeyPatch.context() as monkeypatch:
        api = prime_api.__wrapped__(monkeypatch)
        torch.manual_seed(81)
        model = BackboneModel(api)
        model.model.adapter.lora_dropout = nn.Identity()
        torch.manual_seed(81)
        reference = BackboneModel(api)
        reference.model.adapter.lora_dropout = nn.Identity()
        model.model = ShardedBackbone(model.model)
        install_opsd_head(model, settings())
        api.lm_head._patch_model_forward(model)
        dist.init_process_group('gloo', init_method=(folder / 'init').as_uri(), rank=rank, world_size=2)
        try:
            mesh = init_device_mesh('cpu', (2,))
            fully_shard(model.model.embedding, mesh=mesh)
            fully_shard(model.model.block, mesh=mesh)
            fully_shard(model.lm_head, mesh=mesh, reshard_after_forward=False)
            fully_shard(model, mesh=mesh)
            params = [p for p in model.parameters() if p.requires_grad]
            ref_params = [p for p in reference.parameters() if p.requires_grad]
            optimizer = torch.optim.SGD(params, lr=.1)
            ref_optimizer = torch.optim.SGD(ref_params, lr=.1)
            for step in range(3):
                batches = [batch_for(r, step) for r in range(2)]
                total = sum(b['loss_mask'].sum().item() for b in batches)
                expected = sum(dense_loss(reference, api, b) * b['loss_mask'].sum().item() / total
                               for b in batches)
                expected.backward()
                batch = batches[rank]
                scale = global_loss_scale(batch['loss_mask'].sum().item(), device='cpu')
                assert scale == total / 2
                result = opsd_forward(model, batch, loss_scale=scale, api=api)
                result['loss'].backward()
                actual_loss = result['loss'].detach().clone()
                dist.all_reduce(actual_loss)
                torch.testing.assert_close(actual_loss / 2, expected)
                for param, ref_param in zip(params, ref_params):
                    torch.testing.assert_close(param.grad.full_tensor(), ref_param.grad, rtol=1e-4, atol=1e-7)
                optimizer.step()
                ref_optimizer.step()
                optimizer.zero_grad()
                ref_optimizer.zero_grad()
                for param, ref_param in zip(params, ref_params):
                    torch.testing.assert_close(param.full_tensor(), ref_param, rtol=1e-5, atol=1e-7)
            (folder / f'rank-{rank}.ok').write_text('3 updates; unequal masks and empty rank; dense gradients match\n')
        finally:
            dist.destroy_process_group()


if __name__ == '__main__':
    run(int(sys.argv[1]), Path(sys.argv[2]).resolve())
