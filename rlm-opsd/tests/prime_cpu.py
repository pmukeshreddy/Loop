"""Test-only isolation of byte-identical pinned CPU-capable prime-rl modules.

The full package imports torchtitan/CUDA at models/__init__.py. These tests load
the unchanged base/linear/head files while bypassing those package initializers.
No replacement LoRA forward is supplied by this helper.
"""
import hashlib
import importlib.util
from importlib.metadata import distribution
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import torch
from torch import nn


@pytest.fixture
def prime_api(monkeypatch):
    directory=Path(distribution('prime-rl').locate_file('prime_rl'))
    source=Path(__file__).resolve().parents[1]/'.deps/prime-rl/src/prime_rl'
    for name in ('trainer.models','trainer.models.layers','trainer.models.layers.lora'):
        module=ModuleType('prime_rl.'+name)
        module.__path__=[str(directory/name.replace('.','/'))]
        monkeypatch.setitem(sys.modules,module.__name__,module)
    def load(relative):
        path=directory/(relative.replace('.','/')+'.py')
        assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(
            (source/(relative.replace('.','/')+'.py')).read_bytes()).digest()
        name='prime_rl.'+relative
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules,name,module)
        spec.loader.exec_module(module)
        return module

    base=load('trainer.models.layers.lora.base')
    linear=load('trainer.models.layers.lora.multi_linear')
    lm_head=load('trainer.models.layers.lm_head')
    base.set_lora_num_tokens(torch.tensor([4],dtype=torch.int32))
    base.set_multilora_scaling(torch.tensor([2.0]))
    return SimpleNamespace(base=base,MultiLoRALinear=linear.MultiLoRALinear,lm_head=lm_head)


class TinyModel(nn.Module):
    """Small causal tensor fixture with actual upstream MultiLoRALinear."""
    def __init__(self,api,checkpoint=False):
        super().__init__()
        self.embedding=nn.Embedding(16,8)
        self.projection=api.MultiLoRALinear(nn.Linear(8,16,bias=False),rank=2,n_adapters=1,
                                          alpha=4,dropout=0.25,use_grouped_mm=False)
        with torch.no_grad():self.projection.lora_B[0].normal_(0,0.2)
        for p in self.parameters():p.requires_grad_(False)
        for p in [*self.projection.lora_A,*self.projection.lora_B]:p.requires_grad_(True)
        self.checkpoint=checkpoint

    def features(self,input_ids,position_ids):
        return self.embedding(input_ids).cumsum(1)/(position_ids[...,None]+1)

    def forward(self,input_ids,position_ids):
        x=self.features(input_ids,position_ids)
        if self.checkpoint:
            from torch.utils.checkpoint import checkpoint
            value=checkpoint(self.projection,x,use_reentrant=False)
        else:value=self.projection(x)
        return {'logits':value}


def forward(model,input_ids,position_ids):
    return model(input_ids=input_ids,position_ids=position_ids)
