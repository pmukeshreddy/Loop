"""M6: original rollout IDs and exact causal alignment, without a tokenizer."""
import copy
from types import SimpleNamespace

import pytest


def prefixes():
    return SimpleNamespace(student_ids=(1,2),teacher_ids=(1,7,8,2))


def rollout():
    return dict(error=None,sampling_args={'temperature':0.7},trajectory=[
        dict(tokens=dict(prompt_ids=[1,2],prompt_mask=[0,0],completion_ids=[3,4],
                         completion_mask=[1,1],completion_logprobs=[-0.2,-0.3])),
        dict(tokens=dict(prompt_ids=[1,2,3,4,5,6],prompt_mask=[0]*6,completion_ids=[9,10],
                         completion_mask=[1,0],completion_logprobs=[-0.4,-0.5]))],
        info={'answer':'NEVER_COPY_TO_TRAINING'})


def build(value=None,**kwargs):
    from rlm_opsd.training.samples import samples_from_rollout
    return samples_from_rollout(value or rollout(),prefixes(),max_seq_len=kwargs.get('max_seq_len',20))


def test_multiturn_ids_masks_and_causal_positions_are_exact():
    samples=build()
    assert len(samples)==2
    assert samples[0].student_ids==(1,2,3,4)
    assert samples[0].teacher_ids==(1,7,8,2,3,4)
    assert samples[0].student_positions==(1,2)
    assert samples[0].teacher_positions==(3,4)
    assert samples[0].target_ids==(3,4)
    assert samples[1].student_ids==(1,2,3,4,5,6,9,10)
    assert samples[1].teacher_ids==(1,7,8,2,3,4,5,6,9,10)
    assert samples[1].student_positions==(5,)
    assert samples[1].teacher_positions==(7,)
    assert samples[1].target_ids==(9,)
    assert samples[1].inference_logprobs==(-0.4,)
    assert samples[1].temperature==0.7
    assert 'NEVER_COPY' not in repr(samples)


def test_non_extension_history_still_uses_current_recorded_ids_without_retokenizing():
    value=rollout();value['trajectory'][1]['tokens']['prompt_ids']=[1,2,11,12,13,14]
    sample=build(value)[1]
    assert sample.student_ids==(1,2,11,12,13,14,9,10)
    assert sample.teacher_ids==(1,7,8,2,11,12,13,14,9,10)


@pytest.mark.parametrize('fault', ['missing','prefix','length','bad_id','bad_mask','prompt_loss',
    'nan','positive_logprob','temperature','error','empty','length_limit'])
def test_unusable_rollouts_fail_closed(fault):
    value=rollout();tokens=value['trajectory'][0]['tokens'];kwargs={}
    if fault=='missing':value['trajectory'][0]['tokens']=None
    elif fault=='prefix':tokens['prompt_ids'][0]=99
    elif fault=='length':tokens['completion_logprobs'].pop()
    elif fault=='bad_id':tokens['completion_ids'][0]=True
    elif fault=='bad_mask':tokens['completion_mask'][0]=2
    elif fault=='prompt_loss':tokens['prompt_mask'][0]=1
    elif fault=='nan':tokens['completion_logprobs'][0]=float('nan')
    elif fault=='positive_logprob':tokens['completion_logprobs'][0]=0.1
    elif fault=='temperature':value['sampling_args']['temperature']=0.0
    elif fault=='error':value['error']='rollout failed'
    elif fault=='empty':value['trajectory']=[]
    elif fault=='length_limit':kwargs['max_seq_len']=9
    with pytest.raises(ValueError):build(value,**kwargs)


def test_empty_assistant_mask_is_valid_and_does_not_mutate_the_input():
    value=rollout();original=copy.deepcopy(value)
    for step in value['trajectory']:step['tokens']['completion_mask']=[0,0]
    snapshot=copy.deepcopy(value)
    samples=build(value)
    assert all(not sample.target_ids for sample in samples)
    assert value==snapshot and original['trajectory'][0]['tokens']['completion_mask']==[1,1]


@pytest.mark.parametrize('flag',['is_truncated','overlong_prompt'])
def test_clipped_token_records_cannot_silently_train_on_partial_ids(flag):
    value=rollout();tokens=value['trajectory'][0]['tokens']
    for key in ('completion_ids','completion_mask','completion_logprobs'):
        tokens[key]=tokens[key][:1]
    tokens[flag]=True
    with pytest.raises(ValueError,match='clipp|truncat|overlong'):build(value)


def test_generation_length_stop_with_complete_token_records_is_valid():
    value=rollout();value['trajectory'][0]['finish_reason']='length'
    value['trajectory'][0]['tokens'].update(is_truncated=False,overlong_prompt=False)
    assert build(value)[0].target_ids==(3,4)
