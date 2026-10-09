"""M7 exact full-vocabulary objective; independent probability-space references."""
import math

import pytest
import torch


def dense_reference(student, teacher, mask, *, temperature=1.0, targets=None, gate=False, k=1.0):
    s=(student[mask]/temperature).softmax(-1)
    t=(teacher.detach()[mask]/temperature).softmax(-1)
    mixture=(s+t)/2
    values=((t*(t.log()-mixture.log())).sum(-1)+(s*(s.log()-mixture.log())).sum(-1))/2
    if gate:
        ids=targets[mask,None]
        weights=torch.sigmoid(k*(t.log().gather(1,ids)-s.log().gather(1,ids))).squeeze(1).detach()
        values=values*weights
    return values.sum()/max(1,int(mask.sum()))


def loss(*args,**kwargs):
    from rlm_opsd.training.jsd import masked_jsd_loss
    return masked_jsd_loss(*args,**kwargs)


def test_binary_jsd_matches_hand_computed_value_and_detaches_teacher():
    student=torch.tensor([[.25,.75]],dtype=torch.float64).log().requires_grad_()
    teacher=torch.tensor([[.75,.25]],dtype=torch.float64).log().requires_grad_()
    actual=loss(student,teacher,torch.tensor([True]))
    assert actual.item()==pytest.approx(.75*math.log(1.5)+.25*math.log(.5),abs=1e-12)
    actual.backward()
    expected=.5*.25*.75*math.log(1/3)
    torch.testing.assert_close(student.grad,torch.tensor([[expected,-expected]],dtype=torch.float64))
    assert teacher.grad is None


@pytest.mark.parametrize('dtype',[torch.float64,torch.float32,torch.float16,torch.bfloat16])
def test_identical_distributions_are_zero_with_finite_gradients(dtype):
    student=torch.tensor([[100,-100,0],[.1,.2,.3]],dtype=dtype,requires_grad=True)
    actual=loss(student,student.detach().clone().requires_grad_(),torch.ones(2,dtype=torch.bool))
    assert abs(actual.item())<1e-7
    actual.backward()
    assert torch.isfinite(student.grad).all() and student.grad.abs().max()<1e-6
    assert actual.dtype==(torch.float64 if dtype==torch.float64 else torch.float32)


def test_extreme_finite_logits_reach_log_two_bound_without_nan():
    s=torch.tensor([[10000.,-10000.]],requires_grad=True)
    t=-s.detach()
    result=loss(s,t,torch.tensor([True]));result.backward()
    assert result.item()==pytest.approx(math.log(2),abs=1e-6)
    assert torch.isfinite(s.grad).all()


def test_masks_exclude_nonassistant_rows_and_normalize_selected_count():
    s=torch.tensor([[.25,.75],[.5,.5],[.25,.75]],dtype=torch.float64).log().requires_grad_()
    t=torch.tensor([[.75,.25],[.01,.99],[.25,.75]],dtype=torch.float64).log().requires_grad_()
    with torch.no_grad():s[1].fill_(float('nan'));t[1].fill_(float('nan'))
    actual=loss(s,t,torch.tensor([True,False,True]))
    assert actual.item()==pytest.approx((.75*math.log(1.5)+.25*math.log(.5))/2,abs=1e-12)
    actual.backward()
    assert torch.equal(s.grad[1],torch.zeros(2,dtype=s.dtype)) and t.grad is None


def test_empty_mask_returns_connected_zero_without_teacher_gradient():
    s=torch.full((3,5),float('nan'),requires_grad=True);t=s.detach().clone().requires_grad_()
    result=loss(s,t,torch.zeros(3,dtype=torch.bool))
    assert result.item()==0
    result.backward()
    assert torch.equal(s.grad,torch.zeros_like(s)) and t.grad is None


@pytest.mark.parametrize('gate',[False,True])
def test_gate_uses_aligned_sampled_tokens_and_is_detached(gate):
    s=torch.tensor([[.25,.75],[.75,.25]],dtype=torch.float64).log().requires_grad_()
    t=torch.tensor([[.75,.25],[.25,.75]],dtype=torch.float64).log().requires_grad_()
    mask=torch.tensor([True,True]);targets=torch.tensor([0,0])
    result=loss(s,t,mask,target_ids=targets,token_gate=gate,gate_k=1.)
    base=.75*math.log(1.5)+.25*math.log(.5)
    # The two detached weights are 0.75 and 0.25; divide by tokens, not weight sum.
    assert result.item()==pytest.approx(base*(.5 if gate else 1),abs=1e-12)
    ref_s=s.detach().clone().requires_grad_()
    reference=dense_reference(ref_s,t,mask,targets=targets,gate=gate)
    reference.backward();result.backward()
    torch.testing.assert_close(s.grad,ref_s.grad,rtol=1e-12,atol=1e-12)
    assert t.grad is None


def test_full_vocabulary_tail_affects_loss_even_with_same_sampled_probability():
    s=torch.tensor([[.8,.1,.1]],dtype=torch.float64).log()
    same=s.clone();different=torch.tensor([[.8,.19,.01]],dtype=torch.float64).log()
    mask=torch.tensor([True])
    assert abs(loss(s,same,mask).item())<1e-12
    assert loss(s,different,mask).item()>0.01


@pytest.mark.parametrize('fault',['shape','mask_shape','mask_dtype','integer','nan','temperature',
    'gate_k','missing_targets','target_dtype','target_range'])
def test_invalid_selected_loss_inputs_are_rejected(fault):
    s=torch.randn(2,3);t=torch.randn(2,3);mask=torch.tensor([True,False]);kwargs={}
    if fault=='shape':t=t[:1]
    elif fault=='mask_shape':mask=mask[:1]
    elif fault=='mask_dtype':mask=mask.long()
    elif fault=='integer':s=s.long()
    elif fault=='nan':t[0,0]=float('nan')
    elif fault=='temperature':kwargs['temperature']=0
    elif fault=='gate_k':kwargs['gate_k']=float('nan')
    elif fault=='missing_targets':kwargs['token_gate']=True
    elif fault=='target_dtype':kwargs.update(token_gate=True,target_ids=torch.tensor([0.,1.]))
    elif fault=='target_range':kwargs.update(token_gate=True,target_ids=torch.tensor([3,-100]))
    with pytest.raises(ValueError):loss(s,t,mask,**kwargs)


def test_nonunit_temperature_and_gate_slope_match_independent_reference():
    torch.manual_seed(19)
    s=torch.randn(4,7,dtype=torch.float64,requires_grad=True);t=torch.randn(4,7,dtype=torch.float64)
    mask=torch.tensor([True,False,True,True]);ids=torch.tensor([1,-100,4,6])
    actual=loss(s,t,mask,temperature=.7,token_gate=True,gate_k=3.,target_ids=ids)
    expected=dense_reference(s,t,mask,temperature=.7,targets=ids,gate=True,k=3.)
    torch.testing.assert_close(actual,expected,rtol=1e-12,atol=1e-12)


def chunk_loss(*args,**kwargs):
    from rlm_opsd.training.jsd import chunked_jsd_loss
    return chunked_jsd_loss(*args,**kwargs)


@pytest.mark.parametrize('chunk_size',[1,3,20])
@pytest.mark.parametrize('gate',[False,True])
def test_chunked_projection_matches_dense_values_and_student_gradients(chunk_size,gate):
    torch.manual_seed(37)
    s=torch.randn(9,4,dtype=torch.float64,requires_grad=True)
    t=torch.randn(9,4,dtype=torch.float64,requires_grad=True)
    weight=torch.randn(11,4,dtype=torch.float64)
    mask=torch.tensor([True,False,True,True,False,True,True,True,False])
    targets=torch.tensor([0,-100,2,3,-100,5,6,7,-100])
    actual=chunk_loss(s,t,weight,mask,target_ids=targets,chunk_size=chunk_size,
                      temperature=.8,token_gate=gate,gate_k=2.)
    reference_s=s.detach().clone().requires_grad_()
    expected=dense_reference(reference_s@weight.T,t@weight.T,mask,
                             targets=targets,temperature=.8,gate=gate,k=2.)
    torch.testing.assert_close(actual,expected,rtol=1e-12,atol=1e-12)
    (actual*1.7).backward();(expected*1.7).backward()
    torch.testing.assert_close(s.grad,reference_s.grad,rtol=1e-10,atol=1e-12)
    assert t.grad is None and torch.equal(s.grad[~mask],torch.zeros_like(s.grad[~mask]))


def test_chunked_projection_bounds_both_passes_and_saves_no_vocabulary_activations(monkeypatch):
    torch.manual_seed(10)
    s=torch.randn(13,7,requires_grad=True);t=torch.randn(13,7);weight=torch.randn(101,7)
    mask=torch.tensor([True]*12+[False]);targets=torch.arange(13)
    linear=torch.nn.functional.linear;rows=[];saved=[]
    def observed_linear(values,head,*args,**kwargs):
        rows.append(values.shape[0])
        assert head.data_ptr()==weight.data_ptr()  # No full-head precision copy.
        return linear(values,head,*args,**kwargs)
    monkeypatch.setattr(torch.nn.functional,'linear',observed_linear)
    def pack(tensor):saved.append(tuple(tensor.shape));return tensor
    with torch.autograd.graph.saved_tensors_hooks(pack,lambda tensor:tensor):
        value=chunk_loss(s,t,weight,mask,target_ids=targets,chunk_size=3,token_gate=True)
    assert rows and max(rows)<=3 and sum(rows)==24
    assert not any(len(shape)==2 and shape[-1]==101 for shape in saved)
    rows.clear();value.backward()
    assert rows and max(rows)<=3 and sum(rows)==24
    assert torch.isfinite(s.grad).all()


def test_empty_chunk_mask_does_not_project_and_has_zero_student_gradient(monkeypatch):
    s=torch.full((4,7),float('nan'),requires_grad=True);t=s.detach().clone().requires_grad_()
    def forbidden(*args,**kwargs):raise AssertionError('empty mask must not project')
    monkeypatch.setattr(torch.nn.functional,'linear',forbidden)
    value=chunk_loss(s,t,torch.randn(11,7),torch.zeros(4,dtype=torch.bool),chunk_size=2)
    assert value.item()==0
    value.backward()
    assert torch.equal(s.grad,torch.zeros_like(s)) and t.grad is None


@pytest.mark.parametrize('dtype',[torch.float16,torch.bfloat16])
def test_low_precision_projection_uses_float32_divergence(dtype):
    torch.manual_seed(14)
    s=torch.randn(5,4,dtype=dtype,requires_grad=True);t=torch.randn(5,4,dtype=dtype)
    weight=torch.randn(13,4,dtype=dtype);mask=torch.ones(5,dtype=torch.bool)
    expected=dense_reference((s@weight.T).float(),(t@weight.T).float(),mask)
    result=chunk_loss(s,t,weight,mask,chunk_size=2)
    assert result.dtype==torch.float32
    torch.testing.assert_close(result,expected,rtol=1e-5,atol=1e-6)
    result.backward();assert torch.isfinite(s.grad).all()


def test_chunked_first_order_gradient_passes_finite_difference_check():
    torch.manual_seed(8)
    s=torch.randn(3,2,dtype=torch.float64,requires_grad=True)
    t=torch.randn(3,2,dtype=torch.float64);w=torch.randn(5,2,dtype=torch.float64)
    assert torch.autograd.gradcheck(lambda value:chunk_loss(value,t,w,torch.ones(3,dtype=torch.bool),chunk_size=2),(s,))


@pytest.mark.parametrize('fault',['chunk_size','trainable_head','head_shape','head_dtype','nonfinite_hidden','nonfinite_head'])
def test_chunked_projection_rejects_invalid_or_nonfrozen_inputs(fault):
    s=torch.randn(3,4,requires_grad=True);t=torch.randn(3,4);w=torch.randn(7,4);size=2
    if fault=='chunk_size':size=0
    elif fault=='trainable_head':w.requires_grad_()
    elif fault=='head_shape':w=w[:,:3]
    elif fault=='head_dtype':w=w.double()
    elif fault=='nonfinite_hidden':t[1,0]=float('nan')
    elif fault=='nonfinite_head':w[0,0]=float('nan')
    with pytest.raises(ValueError):chunk_loss(s,t,w,torch.ones(3,dtype=torch.bool),chunk_size=size)


@pytest.mark.parametrize('chunked',[False,True])
@pytest.mark.parametrize('values,temperature',[([3e38,-3e38],1.),([1.,-1.],1e-40)])
def test_normalization_overflow_fails_closed_before_nan_loss_or_gradients(chunked,values,temperature):
    s=torch.tensor([values],requires_grad=True);t=-s.detach();mask=torch.tensor([True])
    # These finite inputs exceed FP32's normalization range. Fail explicitly;
    # do not clamp probabilities or silently produce an unusable NaN objective.
    with pytest.raises(ValueError,match='normaliz'):
        if chunked:chunk_loss(s,t,torch.eye(2),mask,chunk_size=1,temperature=temperature)
        else:loss(s,t,mask,temperature=temperature)
    assert s.grad is None


@pytest.mark.parametrize('setting',[{'temperature':1e-40},{'gate_k':1e300}])
def test_unrepresentable_scalars_reject_even_when_identical_logits_hide_forward_overflow(setting):
    s=torch.zeros(1,2,requires_grad=True);mask=torch.tensor([True])
    with pytest.raises(ValueError,match='precision'):
        loss(s,s.detach(),mask,target_ids=torch.tensor([0]),token_gate=True,**setting)
    assert s.grad is None
