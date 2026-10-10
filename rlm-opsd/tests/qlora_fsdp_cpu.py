"""Exercise NF4 FSDP2 sharding and native DCP state/optimizer resume on CPU."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch
import torch.distributed as dist
from torch.distributed.checkpoint import save, load
from torch.distributed.device_mesh import init_device_mesh
from torch.distributed.fsdp import fully_shard, MixedPrecisionPolicy
from torch.distributed.algorithms._checkpoint.checkpoint_wrapper import checkpoint_wrapper
from transformers import LlamaConfig, LlamaForCausalLM

from prime_cpu import prime_api, prime_checkpoint
from test_training_qlora import attach_adapter
from test_prime_opsd_step import micro_batch, settings
from rlm_opsd.training.qlora import load_nf4_weights, NF4Linear
from rlm_opsd.training.prime_step import install_opsd_head, opsd_forward, global_loss_scale


def run(rank, folder, checkpoint):
    torch.set_num_threads(1)
    with pytest.MonkeyPatch.context() as monkeypatch:
        api = prime_api.__wrapped__(monkeypatch)
        checkpoint_api = prime_checkpoint.__wrapped__(api, monkeypatch)
        dist.init_process_group('gloo', init_method=(folder / 'rendezvous').as_uri(), rank=rank, world_size=2)
        try:
            mesh = init_device_mesh('cpu', (2,))
            policy = MixedPrecisionPolicy(param_dtype=torch.bfloat16, reduce_dtype=torch.float32)

            def setup():
                config = LlamaConfig.from_pretrained(folder)
                config._attn_implementation = 'eager'
                with torch.device('meta'):
                    skeleton = LlamaForCausalLM(config)
                model = load_nf4_weights(skeleton,
                    SimpleNamespace(name=str(folder), trust_remote_code=False), torch.device('cpu'))
                torch.manual_seed(17)
                attach_adapter(model, api)
                # Match the native optimizer precision; packed weights stay BF16.
                for param in model.parameters():
                    if param.requires_grad:
                        param.data = param.data.float()
                install_opsd_head(model, settings())
                api.lm_head._patch_model_forward(model)
                for idx, layer in enumerate(model.model.layers):
                    if checkpoint:
                        layer = checkpoint_wrapper(layer, preserve_rng_state=True)
                    model.model.layers[idx] = layer
                    fully_shard(layer, mesh=mesh, mp_policy=policy)
                fully_shard(model.model.embed_tokens, mesh=mesh, mp_policy=policy)
                fully_shard([model.lm_head, model.model.norm], mesh=mesh, mp_policy=policy,
                            reshard_after_forward=False)
                fully_shard(model, mesh=mesh, mp_policy=policy)
                model.train()
                optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=.01)
                return model, optimizer

            model, optimizer = setup()
            packed = {name: module.weight.to_local().view(torch.uint8).clone()
                      for name, module in model.named_modules() if isinstance(module, NF4Linear)}
            assert all(module.weight.to_local().numel() * 8 == module.in_features * module.out_features
                       for module in model.modules() if isinstance(module, NF4Linear))

            def step(model, optimizer, empty=False):
                batch = micro_batch(empty=empty)
                scale = global_loss_scale(batch['loss_mask'].sum().item(), device='cpu')
                output = opsd_forward(model, batch, loss_scale=scale, api=api)
                assert torch.isfinite(output['loss'])
                output['loss'].backward()
                assert all(p.grad is not None and torch.isfinite(p.grad.to_local()).all()
                           for p in model.parameters() if p.requires_grad)
                optimizer.step()
                optimizer.zero_grad()
                return output['loss'].detach()

            scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=.5)
            step(model, optimizer)
            scheduler.step()
            app = checkpoint_api.AppState(model, [optimizer], scheduler, None)
            save({'app': app}, checkpoint_id=folder / 'checkpoint')
            expected = step(model, optimizer, empty=rank == 1)
            reference = {name: p.full_tensor().clone() for name, p in model.named_parameters() if p.requires_grad}
            for name, module in model.named_modules():
                if name in packed:
                    assert torch.equal(module.weight.to_local().view(torch.uint8), packed[name])
            # A fresh NF4 model: reload quantization buffers, adapter and optimizer.
            restored, optimizer = setup()
            restored_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=.5)
            restored_app = checkpoint_api.AppState(restored, [optimizer], restored_scheduler, None)
            load({'app': restored_app}, checkpoint_id=folder / 'checkpoint')
            assert restored_scheduler.state_dict() == scheduler.state_dict()
            actual = step(restored, optimizer, empty=rank == 1)
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
            for name, param in restored.named_parameters():
                if param.requires_grad:
                    torch.testing.assert_close(param.full_tensor(), reference[name], rtol=0, atol=0)
            (folder / f'qlora-rank-{rank}.ok').write_text('NF4/BF16 FSDP updates and exact checkpoint continuation passed\n')
        finally:
            dist.destroy_process_group()


if __name__ == '__main__':
    run(int(sys.argv[1]), Path(sys.argv[2]).resolve(), bool(int(sys.argv[3])))
