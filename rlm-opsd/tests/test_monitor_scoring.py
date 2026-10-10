"""CPU tensor fixtures, not pretrained or GPU evaluation evidence."""
from dataclasses import replace
import math

import pytest
import torch
from prime_cpu import prime_api
from test_training_opsd import BackboneModel
from test_training_samples import build


def api():
    from rlm_opsd.eval import scoring
    return scoring


def dense(model,prime,sample):
    from rlm_opsd.training.teacher import frozen_teacher
    model.eval()
    prime.base.set_lora_num_tokens(torch.tensor([len(sample.student_ids)],dtype=torch.int32))
    with torch.no_grad():
        s=model.model(torch.tensor([sample.student_ids]),torch.arange(len(sample.student_ids))[None,:]).last_hidden_state
        s=(s[0,list(sample.student_positions)]@model.lm_head.weight.T).double()/sample.temperature
        with frozen_teacher(model,len(sample.teacher_ids),api=prime):
            t=model.model(torch.tensor([sample.teacher_ids]),torch.arange(len(sample.teacher_ids))[None,:]).last_hidden_state
            t=(t[0,list(sample.teacher_positions)]@model.lm_head.weight.T).double()/sample.temperature
    s=s.softmax(-1);t=t.softmax(-1)
    return (t*(t.log()-s.log())).sum(-1),-(s*s.log()).sum(-1)


@pytest.mark.parametrize('chunk_size',[1,3])
def test_local_kl_equals_independent_dense_and_restores_state(prime_api,chunk_size,monkeypatch):
    from torch.nn import functional as F
    torch.manual_seed(7);model=BackboneModel(prime_api)
    sample=replace(build()[0],temperature=.7)
    expected_kl,expected_h=dense(model,prime_api,sample)
    model.train();model.model.embedding.eval()
    flags=[m.training for m in model.modules()]
    prime_api.base.set_lora_num_tokens(torch.tensor([4],dtype=torch.int32))
    original=F.linear;projected=[]
    def linear(x,w,*args):
        if w is model.lm_head.weight:projected.append(x.shape[0])
        return original(x,w,*args)
    monkeypatch.setattr(F,'linear',linear)
    result=api().score_samples(model,[sample],chunk_size=chunk_size,api=prime_api)[0]
    torch.testing.assert_close(torch.tensor(result['kl'],dtype=torch.float64),expected_kl,atol=1e-6,rtol=1e-5)
    assert 'entropy' not in result
    assert projected and max(projected)<=chunk_size
    assert [m.training for m in model.modules()]==flags
    assert prime_api.base.get_lora_num_tokens().tolist()==[4]
    assert prime_api.base.get_multilora_scaling().tolist()==[2]
    assert all(p.grad is None for p in model.parameters())


def test_scoring_zero_kl_for_identical_inputs_and_no_adapter(prime_api):
    model=BackboneModel(prime_api)
    with torch.no_grad():model.model.adapter.lora_B[0].zero_()
    s=build()[0];s=replace(s,teacher_ids=s.student_ids,teacher_positions=s.student_positions)
    result=api().score_samples(model,[s],chunk_size=1,api=prime_api)[0]
    assert result['kl']==pytest.approx([0.]*len(s.target_ids),abs=1e-7)
    assert 'entropy' not in result


def test_scoring_failure_restores_modes_and_routing(prime_api):
    model=BackboneModel(prime_api);flags=[m.training for m in model.modules()]
    with torch.no_grad():model.lm_head.weight.fill_(float('nan'))
    with pytest.raises(ValueError):api().score_samples(model,build(),chunk_size=1,api=prime_api)
    assert [m.training for m in model.modules()]==flags
    assert prime_api.base.get_lora_num_tokens().tolist()==[4]
    assert 'forward' not in model.model.adapter.__dict__


def test_offset_mapping_keeps_original_unicode_and_special_token_ids():
    from rlm_opsd.prompts.chat import load_tokenizer,PromptConfig
    tokenizer=load_tokenizer(PromptConfig.from_yaml())
    text='Think é 🌍\n```repl\n# comment\nllm_query("x")\n```\nFINAL(ok)<|im_end|>'
    ids=tokenizer.encode(text,add_special_tokens=False)
    mapped=api().token_offsets(tokenizer,ids)
    assert mapped['text']==text
    assert len(mapped['offsets'])==len(ids)
    assert mapped['offsets'][-1]==(0,0)
    assert mapped['token_ids']==ids
    assert any(a==b for a,b in zip(mapped['offsets'],mapped['offsets'][1:])) # Unicode byte pieces


def test_non_roundtripping_tokenization_is_not_silently_realigned():
    from rlm_opsd.prompts.chat import load_tokenizer,PromptConfig
    tokenizer=load_tokenizer(PromptConfig.from_yaml())
    # Two separately encoded fragments merge under canonical encoding.
    ids=tokenizer.encode('he',add_special_tokens=False)+tokenizer.encode('llo',add_special_tokens=False)
    with pytest.raises(ValueError,match='round.trip'):api().token_offsets(tokenizer,ids)


@pytest.mark.parametrize('fault',[None,'missing','extra','shape','nonfinite','hash'])
def test_adapter_checkpoint_is_exact_and_atomic(prime_api,tmp_path,fault):
    from rlm_opsd.eval.preflight import sha256
    model=BackboneModel(prime_api)
    before={n:p.detach().clone() for n,p in model.named_parameters()}
    state={n:torch.full_like(p,.25) for n,p in model.named_parameters() if p.requires_grad}
    if fault=='missing':state.pop(next(iter(state)))
    if fault=='extra':state['base.weight']=torch.ones(1)
    if fault=='shape':state[next(iter(state))]=torch.ones(1)
    if fault=='nonfinite':state[next(iter(state))].fill_(float('nan'))
    path=tmp_path/'adapter.pt';torch.save(state,path)
    checksum='0'*64 if fault=='hash' else sha256(path)
    if fault:
        with pytest.raises(ValueError):api().load_adapter(model,path,checksum,api=prime_api)
        assert all(torch.equal(p,before[n]) for n,p in model.named_parameters())
    else:
        api().load_adapter(model,path,checksum,api=prime_api)
        for n,p in model.named_parameters():
            assert torch.equal(p,state[n] if n in state else before[n])
