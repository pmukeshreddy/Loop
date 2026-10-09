"""M7 actual LoRA/backbone integration; random CPU fixtures, not pretrained runs."""
import math
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from prime_cpu import prime_api
from test_training_jsd import dense_reference
from test_training_samples import build, rollout


class Backbone(nn.Module):
    def __init__(self,api,checkpoint):
        super().__init__()
        self.embedding=nn.Embedding(16,8)
        self.adapter=api.MultiLoRALinear(nn.Linear(8,8,bias=False),rank=2,n_adapters=1,
                                        alpha=4,dropout=.25,use_grouped_mm=False)
        with torch.no_grad():self.adapter.lora_B[0].normal_(0,.2)
        self.checkpoint=checkpoint

    def forward(self,input_ids,position_ids,**kwargs):
        x=self.embedding(input_ids).cumsum(1)/(position_ids[...,None]+1)
        if self.checkpoint:
            from torch.utils.checkpoint import checkpoint
            x=checkpoint(self.adapter,x,use_reentrant=False)
        else:x=self.adapter(x)
        return SimpleNamespace(last_hidden_state=x)


class BackboneModel(nn.Module):
    def __init__(self,api,checkpoint=False):
        super().__init__()
        self.model=Backbone(api,checkpoint)
        self.lm_head=nn.Linear(8,16,bias=False)
        for p in self.parameters():p.requires_grad_(False)
        for p in [*self.model.adapter.lora_A,*self.model.adapter.lora_B]:p.requires_grad_(True)

    def forward(self,*args,**kwargs):
        raise AssertionError('Mode B must never materialize full-sequence model logits')


def reference_step(model,api,samples,*,gate):
    from rlm_opsd.training.teacher import frozen_teacher
    total=sum(len(s.target_ids) for s in samples);value=0.
    for sample in samples:
        api.base.set_lora_num_tokens(torch.tensor([len(sample.student_ids)],dtype=torch.int32))
        s=model.model(torch.tensor([sample.student_ids]),torch.arange(len(sample.student_ids))[None,:]).last_hidden_state
        s=s[0,list(sample.student_positions)]@model.lm_head.weight.T
        with frozen_teacher(model,len(sample.teacher_ids),api=api):
            t=model.model(torch.tensor([sample.teacher_ids]),torch.arange(len(sample.teacher_ids))[None,:]).last_hidden_state
            t=t[0,list(sample.teacher_positions)]@model.lm_head.weight.T
        loss=dense_reference(s,t,torch.ones(len(sample.target_ids),dtype=torch.bool),
            temperature=sample.temperature,targets=torch.tensor(sample.target_ids),gate=gate,k=2.)
        weighted=loss*len(sample.target_ids)/total
        value+=float(weighted.detach());weighted.backward()
    return value


@pytest.mark.parametrize('checkpoint',[False,True])
@pytest.mark.parametrize('gate',[False,True])
def test_mode_b_matches_dense_multiturn_loss_and_lora_gradient(prime_api,checkpoint,gate):
    from rlm_opsd.training.mode_b import ModeBTrainer
    torch.manual_seed(9);model=BackboneModel(prime_api,checkpoint)
    torch.manual_seed(9);reference=BackboneModel(prime_api,checkpoint)
    samples=build()
    torch.manual_seed(17);expected=reference_step(reference,prime_api,samples,gate=gate)
    prime_api.base.set_lora_num_tokens(torch.tensor([4],dtype=torch.int32))
    trainer=ModeBTrainer(model,api=prime_api,chunk_size=1,token_gate=gate,gate_k=2.,max_grad_norm=1000.)
    before={n:p.detach().clone() for n,p in model.named_parameters()}
    torch.manual_seed(17);result=trainer.step(samples)
    assert result['updated'] and result['assistant_tokens']==3
    assert result['loss']==pytest.approx(expected,rel=1e-5,abs=1e-7)
    changed=[]
    for (name,p),(other,q) in zip(model.named_parameters(),reference.named_parameters()):
        assert name==other
        if p.requires_grad:
            torch.testing.assert_close(p.grad,q.grad,rtol=1e-4,atol=1e-7)
            if not torch.equal(p,before[name]):changed.append(name)
        else:assert p.grad is None and torch.equal(p,before[name])
    assert changed and all('lora_' in n for n in changed)
    assert prime_api.base.get_lora_num_tokens().tolist()==[4]


def test_teacher_hidden_is_base_only_and_fixed_after_updates(prime_api):
    from rlm_opsd.training.mode_b import ModeBTrainer,backbone_hidden
    from rlm_opsd.training.teacher import frozen_teacher
    torch.manual_seed(10);model=BackboneModel(prime_api);sample=build()[0]
    ids=torch.tensor([sample.teacher_ids]);pos=torch.arange(ids.shape[1])[None,:]
    with frozen_teacher(model,len(sample.teacher_ids),api=prime_api):before=backbone_hidden(model,ids,pos).clone()
    trainer=ModeBTrainer(model,api=prime_api,chunk_size=1,learning_rate=.01)
    for _ in range(2):assert trainer.step([sample])['updated']
    with frozen_teacher(model,len(sample.teacher_ids),api=prime_api):after=backbone_hidden(model,ids,pos)
    torch.testing.assert_close(before,after,rtol=0,atol=0)
    assert not before.requires_grad and not after.requires_grad


def test_empty_mask_mode_b_skips_all_forwards_and_updates(prime_api):
    from rlm_opsd.training.mode_b import ModeBTrainer
    model=BackboneModel(prime_api);before={n:p.detach().clone() for n,p in model.named_parameters()}
    value=rollout()
    for step in value['trajectory']:step['tokens']['completion_mask']=[0,0]
    def forbidden(*args):raise AssertionError('empty mask forwarded')
    result=ModeBTrainer(model,api=prime_api,hidden_fn=forbidden).step(build(value))
    assert result==dict(loss=0.,assistant_tokens=0,gradient_norm=0.,updated=False)
    assert all(torch.equal(p,before[n]) for n,p in model.named_parameters())


@pytest.mark.parametrize('fault',['teacher','projection'])
def test_mode_b_error_restores_state_and_does_not_update(prime_api,fault):
    from rlm_opsd.training.mode_b import ModeBTrainer,backbone_hidden
    model=BackboneModel(prime_api);before={n:p.detach().clone() for n,p in model.named_parameters()}
    initial_flags=[m.training for m in model.modules()]
    def hidden(model,ids,pos):
        if ids.shape[1]==6 and fault=='teacher':raise RuntimeError('injected teacher failure')
        value=backbone_hidden(model,ids,pos)
        return value*float('nan') if fault=='projection' else value
    trainer=ModeBTrainer(model,api=prime_api,hidden_fn=hidden)
    with pytest.raises((RuntimeError,ValueError)):trainer.step([build()[0]])
    assert all(torch.equal(p,before[n]) for n,p in model.named_parameters())
    assert all(p.grad is None for p in model.parameters())
    assert [m.training for m in model.modules()]==initial_flags
    assert 'forward' not in model.model.adapter.__dict__
    assert prime_api.base.get_lora_num_tokens().tolist()==[4]
    assert prime_api.base.get_multilora_scaling().tolist()==[2]


@pytest.mark.parametrize('fault',['bias','custom_head','trainable','softcap','chunk','gate','learning_rate'])
def test_mode_b_rejects_unsupported_head_and_settings(prime_api,fault):
    from rlm_opsd.training.mode_b import ModeBTrainer
    model=BackboneModel(prime_api);kwargs={}
    if fault=='bias':model.lm_head.bias=nn.Parameter(torch.zeros(16),requires_grad=False)
    elif fault=='custom_head':model.lm_head=nn.Identity()
    elif fault=='trainable':model.lm_head.weight.requires_grad_(True)
    elif fault=='softcap':model.config=SimpleNamespace(final_logit_softcapping=2.)
    elif fault=='chunk':kwargs['chunk_size']=0
    elif fault=='gate':kwargs['gate_k']=float('inf')
    elif fault=='learning_rate':kwargs['learning_rate']=0
    with pytest.raises(ValueError):ModeBTrainer(model,api=prime_api,**kwargs)


def test_random_tiny_qwen_mode_b_bypasses_full_head_and_updates_adapter(prime_api):
    from transformers import Qwen3_5Config,Qwen3_5ForConditionalGeneration
    from rlm_opsd.training.mode_b import ModeBTrainer
    torch.manual_seed(23)
    cfg=Qwen3_5Config(text_config=dict(vocab_size=16,hidden_size=16,intermediate_size=32,
        num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,head_dim=8,
        layer_types=['full_attention'],use_cache=False,rope_parameters={'rope_type':'default',
            'rope_theta':10000.0,'partial_rotary_factor':1.0,'mrope_section':[1,1,2]}),
        vision_config=dict(depth=1,hidden_size=16,intermediate_size=32,num_heads=2,
                           out_hidden_size=16,num_position_embeddings=16))
    cfg._attn_implementation='eager';model=Qwen3_5ForConditionalGeneration(cfg)
    attention=model.model.language_model.layers[0].self_attn
    attention.q_proj=prime_api.MultiLoRALinear(attention.q_proj,rank=2,n_adapters=1,
                                             alpha=4,dropout=0.,use_grouped_mm=False)
    for p in model.parameters():p.requires_grad_(False)
    for p in [*attention.q_proj.lora_A,*attention.q_proj.lora_B]:p.requires_grad_(True)
    def forbidden(*args):raise AssertionError('full head invoked')
    handle=model.lm_head.register_forward_pre_hook(forbidden)
    try:result=ModeBTrainer(model,api=prime_api,chunk_size=1,token_gate=True).step([build()[0]])
    finally:handle.remove()
    assert result['updated'] and result['gradient_norm']>0 and math.isfinite(result['loss'])
    assert torch.count_nonzero(attention.q_proj.lora_B[0])>0
    assert model.lm_head.weight.grad is None
