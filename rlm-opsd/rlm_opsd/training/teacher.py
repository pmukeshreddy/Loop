"""Serialized, temporary frozen-base forward for pinned dense MultiLoRA."""
from contextlib import contextmanager
import threading
from types import MethodType, SimpleNamespace

import torch


FORWARD_LOCK=threading.RLock()
_MISSING=object()


def prime_lora_api():
    from prime_rl.trainer.models.layers.lora import base, MultiLoRALinear
    return SimpleNamespace(base=base,MultiLoRALinear=MultiLoRALinear)


def checked_adapters(model,api,*,allow_fsdp=False):
    from torch.distributed.fsdp import FSDPModule
    adapters=[]
    for module in model.modules():
        if (isinstance(module,FSDPModule) and not allow_fsdp) or hasattr(module,'_orig_mod'):
            raise ValueError('M6 supports eager unsharded models; FSDP/compile are unsupported')
        if isinstance(module,api.base.MultiLoRAModule):
            if type(module) is not api.MultiLoRALinear:
                raise ValueError('unsupported adapter: M6 requires dense MultiLoRALinear')
            if module.n_adapters!=1:
                raise ValueError('M6 requires one adapter')
            if (module._lora_num_tokens is not api.base.get_lora_num_tokens()
                    or module._scaling_factors is not api.base.get_multilora_scaling()):
                raise ValueError('adapter uses stale global tensor references')
            adapters.append(module)
    if not adapters:
        raise ValueError('model must contain pinned MultiLoRA adapters')
    allowed={id(p) for m in adapters for p in [*m.lora_A,*m.lora_B]}
    if any(p.requires_grad and id(p) not in allowed for p in model.parameters()):
        raise ValueError('all non-LoRA base parameters must remain frozen')
    if any(p.device.type not in ('cpu','cuda') for p in model.parameters()):
        raise ValueError('M6 supports CPU tensor tests or CUDA runtime')
    return adapters


def _base_only(self,x):
    # A true bypass: adapter matmuls/dropout never run, including for NaN weights.
    return self.base_layer(x)


@contextmanager
def frozen_teacher(model, token_count, *, api=None, allow_fsdp=False):
    api=api or prime_lora_api()
    if type(token_count) is not int or token_count<=0:
        raise ValueError('teacher token count must be positive')
    with FORWARD_LOCK:
        adapters=checked_adapters(model,api,allow_fsdp=allow_fsdp)
        base=api.base
        counts=base.get_lora_num_tokens().clone();scales=base.get_multilora_scaling().clone()
        if counts.shape!=(1,) or scales.shape!=(1,):
            raise ValueError('M6 requires single-run routing tensors')
        modes=[(m,m.training) for m in model.modules()]
        forwards=[(m,m.__dict__.get('forward',_MISSING)) for m in adapters]
        devices=sorted({p.device.index for p in model.parameters() if p.device.type=='cuda'})
        with torch.random.fork_rng(devices=devices),torch.no_grad():
            try:
                base.set_lora_num_tokens(torch.full_like(counts,token_count))
                base.set_multilora_scaling(torch.zeros_like(scales))
                model.eval()
                for module,_ in forwards:module.forward=MethodType(_base_only,module)
                yield
            finally:
                for module,previous in forwards:
                    if previous is _MISSING:
                        if 'forward' in module.__dict__:del module.forward
                    else:module.forward=previous
                for module,training in modes:module.training=training
                base.set_lora_num_tokens(counts)
                base.set_multilora_scaling(scales)
