import math
import threading

import pytest
import torch

from prime_cpu import prime_api, TinyModel, forward
from test_training_samples import build, rollout


def test_random_tiny_qwen35_graph_with_frozen_head_and_pinned_lora(prime_api):
    """Real model classes, random tiny weights; NOT either pretrained smoke."""
    from transformers import Qwen3_5Config,Qwen3_5ForConditionalGeneration
    from rlm_opsd.training.teacher import frozen_teacher
    from rlm_opsd.training.opsd import OpsdTrainer, backbone_hidden
    torch.manual_seed(23)
    cfg=Qwen3_5Config(text_config=dict(vocab_size=16,hidden_size=16,intermediate_size=32,
        num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,head_dim=8,
        layer_types=['full_attention'],use_cache=False,rope_parameters={'rope_type':'default',
            'rope_theta':10000.0,'partial_rotary_factor':1.0,'mrope_section':[1,1,2]}),
        vision_config=dict(depth=1,hidden_size=16,intermediate_size=32,num_heads=2,
                           out_hidden_size=16,num_position_embeddings=16))
    cfg._attn_implementation='eager'
    model=Qwen3_5ForConditionalGeneration(cfg)
    attention=model.model.language_model.layers[0].self_attn
    base=attention.q_proj
    attention.q_proj=prime_api.MultiLoRALinear(base,rank=2,n_adapters=1,alpha=4,
                                             dropout=0.0,use_grouped_mm=False)
    for p in model.parameters():p.requires_grad_(False)
    for p in [*attention.q_proj.lora_A,*attention.q_proj.lora_B]:p.requires_grad_(True)
    sample=build()[0]
    ids=torch.tensor([sample.teacher_ids]);positions=torch.arange(ids.shape[1])[None,:]
    with frozen_teacher(model,ids.shape[1],api=prime_api):
        teacher_before=model.lm_head(backbone_hidden(model,ids,positions)).detach()
    trainer=OpsdTrainer(model,api=prime_api,learning_rate=0.01)
    result=trainer.step([sample])
    assert result['updated'] and result['gradient_norm']>0
    assert torch.count_nonzero(attention.q_proj.lora_B[0])>0
    with frozen_teacher(model,ids.shape[1],api=prime_api):
        teacher_after=model.lm_head(backbone_hidden(model,ids,positions)).detach()
    torch.testing.assert_close(teacher_after,teacher_before,rtol=0,atol=0)
    assert all(p.grad is None for p in model.parameters() if not p.requires_grad)


def test_teacher_is_exact_frozen_base_and_no_grad_even_with_nonfinite_adapter(prime_api):
    from rlm_opsd.training.teacher import frozen_teacher
    model=TinyModel(prime_api)
    ids=torch.tensor([[1,7,8,2,3,4]]);positions=torch.arange(6)[None,:]
    expected=model.projection.base_layer(model.features(ids,positions)).detach()
    with torch.no_grad():model.projection.lora_B[0].fill_(float('nan'))
    with frozen_teacher(model,6,api=prime_api):
        result=forward(model,ids,positions)['logits']
        assert not result.requires_grad
        assert not model.training and not model.projection.training
        assert torch.isfinite(result).all()
        torch.testing.assert_close(result,expected,rtol=0,atol=0)
    assert model.training


def test_teacher_restores_tensor_references_modes_rng_and_forward_on_exception(prime_api):
    from rlm_opsd.training.teacher import frozen_teacher
    model=TinyModel(prime_api);model.embedding.eval()
    base=prime_api.base;counts=base.get_lora_num_tokens();scales=base.get_multilora_scaling()
    rng=torch.get_rng_state().clone();before_flags=[m.training for m in model.modules()]
    with pytest.raises(RuntimeError,match='injected'):
        with frozen_teacher(model,9,api=prime_api):
            assert counts.tolist()==[9] and scales.tolist()==[0]
            torch.rand(5)
            raise RuntimeError('injected')
    assert counts is base.get_lora_num_tokens() and scales is base.get_multilora_scaling()
    assert counts.tolist()==[4] and scales.tolist()==[2]
    assert 'forward' not in model.projection.__dict__
    assert [m.training for m in model.modules()]==before_flags
    assert torch.equal(torch.get_rng_state(),rng)


def test_teacher_rejects_trainable_base_and_unsupported_adapters(prime_api):
    from rlm_opsd.training.teacher import frozen_teacher
    model=TinyModel(prime_api);model.embedding.weight.requires_grad_(True)
    with pytest.raises(ValueError,match='frozen'):
        with frozen_teacher(model,4,api=prime_api):pass
    model.embedding.weight.requires_grad_(False)
    class UnknownAdapter(prime_api.base.MultiLoRAModule):
        def named_parameters_for_adapter(self,idx):return []
        def get_lora_param_counts(self):return (0,0)
    model.extra=UnknownAdapter(torch.nn.Identity())
    with pytest.raises(ValueError,match='unsupported'):
        with frozen_teacher(model,4,api=prime_api):pass


def test_teacher_context_serializes_shared_global_routing(prime_api):
    from rlm_opsd.training.teacher import frozen_teacher
    model=TinyModel(prime_api);attempted=threading.Event();entered=threading.Event()
    def other():
        attempted.set()
        with frozen_teacher(model,8,api=prime_api):entered.set()
    with frozen_teacher(model,6,api=prime_api):
        thread=threading.Thread(target=other);thread.start()
        assert attempted.wait(2)
        assert not entered.wait(0.05)
        assert prime_api.base.get_lora_num_tokens().tolist()==[6]
    thread.join(2)
    assert not thread.is_alive() and entered.is_set()
    assert prime_api.base.get_lora_num_tokens().tolist()==[4]


@pytest.mark.parametrize('checkpoint',[False,True])
def test_teacher_second_pass_preserves_student_backward_and_dropout_rng(prime_api,checkpoint):
    from rlm_opsd.training.teacher import frozen_teacher
    torch.manual_seed(13);model=TinyModel(prime_api,checkpoint)
    torch.manual_seed(13);reference=TinyModel(prime_api,checkpoint)
    ids=torch.tensor([[1,2,3,4]]);pos=torch.arange(4)[None,:]
    torch.manual_seed(22);student=forward(model,ids,pos)['logits']
    with frozen_teacher(model,6,api=prime_api):
        forward(model,torch.tensor([[1,7,8,2,3,4]]),torch.arange(6)[None,:])
    student.sum().backward()
    torch.manual_seed(22);forward(reference,ids,pos)['logits'].sum().backward()
    for (name,p),(other,q) in zip(model.named_parameters(),reference.named_parameters()):
        assert name==other
        if p.requires_grad:torch.testing.assert_close(p.grad,q.grad,rtol=0,atol=0)
        else:assert p.grad is None and q.grad is None


def test_opsd_step_updates_only_lora_and_base_teacher_stays_fixed(prime_api):
    from rlm_opsd.training.opsd import OpsdTrainer
    from rlm_opsd.training.teacher import frozen_teacher
    from test_training_opsd import BackboneModel
    from rlm_opsd.training.opsd import backbone_hidden
    torch.manual_seed(3);model=BackboneModel(prime_api)
    before={name:p.detach().clone() for name,p in model.named_parameters()}
    trainer=OpsdTrainer(model,api=prime_api,learning_rate=0.01)
    sample=build()[0]
    result=trainer.step([sample])
    assert result['updated'] and result['assistant_tokens']==2 and math.isfinite(result['loss'])
    assert result['gradient_norm']>0
    changed=[]
    for name,p in model.named_parameters():
        if not torch.equal(before[name],p):changed.append(name)
        if not p.requires_grad:assert torch.equal(before[name],p) and p.grad is None
    assert changed and all('lora_' in name for name in changed)
    ids=torch.tensor([sample.teacher_ids]);positions=torch.arange(ids.shape[1])[None,:]
    expected=model.model.adapter.base_layer(model.model.embedding(ids).cumsum(1)/(positions[...,None]+1)).detach()
    with frozen_teacher(model,len(sample.teacher_ids),api=prime_api):
        torch.testing.assert_close(backbone_hidden(model,ids,positions),expected,rtol=0,atol=0)


def test_empty_mask_step_makes_no_update(prime_api):
    from rlm_opsd.training.opsd import OpsdTrainer
    from test_training_opsd import BackboneModel
    model=BackboneModel(prime_api);before={n:p.detach().clone() for n,p in model.named_parameters()}
    value=rollout()
    for s in value['trajectory']:s['tokens']['completion_mask']=[0,0]
    def must_not_forward(*args,**kwargs):raise AssertionError('empty mask should not run a model')
    trainer=OpsdTrainer(model,hidden_fn=must_not_forward,api=prime_api)
    result=trainer.step(build(value))
    assert result==dict(loss=0.0,assistant_tokens=0,gradient_norm=0.0,updated=False)
    assert all(torch.equal(before[n],p) for n,p in model.named_parameters())
