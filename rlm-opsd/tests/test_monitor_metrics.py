"""Hand-derived M8 monitoring values; never model-performance evidence."""
import math
import pytest


def api():
    from rlm_opsd.eval import metrics
    return metrics


@pytest.mark.parametrize('kind,prediction,answer,score', [
    ('exact','  Paris  ','Paris',1.),('exact','paris','Paris',0.),
    ('numeric','2.00',2,1.),('numeric','2.1',2,0.),('numeric','nan',2,0.),
    ('multiple_choice','B','B',1.),('multiple_choice','The answer is B','B',0.),
    ('list_f1','["a", "b"]',['b','c'],.5),('list_f1',"['a', 'b']",['a','b'],1.),
    ('list_f1','[]',[],1.),('list_f1','not a list',['a'],0.),
])
def test_answer_scores_are_explicit_and_not_fuzzy(kind,prediction,answer,score):
    assert api().score_answer(prediction,answer,kind)==score


@pytest.mark.parametrize('final', [dict(type='none',value='yes',error=None),
    dict(type='FINAL',value='yes',error='bad'),dict(type='FINAL_VAR',value='yes',error='missing')])
def test_malformed_finish_never_scores(final):
    assert api().score_trajectory({'final':final},'yes','exact')==0.


def test_valid_finish_and_partial_list_score():
    assert api().score_trajectory({'final':dict(type='FINAL_VAR',value='[1, 2]',error=None)},[2,3],'list_f1')==.5
    with pytest.raises(ValueError):api().score_answer('x','x','fuzzy')


def test_divergence_summary_weights_tokens_and_preserves_turn_and_source():
    from rlm_opsd.eval.monitor_reports import summarize_divergence
    turns=[dict(turn_index=0,text='Hi FINAL(x)',offsets=[(0,2),(3,8),(0,0)],values=[1.,3.,5.],trajectory_path='a.json'),
           dict(turn_index=0,text='Hi',offsets=[(0,2)],values=[7.],trajectory_path='b.json'),
           dict(turn_index=1,text='Yo',offsets=[(0,2)],values=[9.],trajectory_path='a.json')]
    r=summarize_divergence(turns,top_k=2)
    assert r['overall']==dict(count=5,sum=25.,mean=5.)
    assert r['by_category']['prose']==dict(count=3,sum=17.,mean=pytest.approx(17/3))
    assert r['by_category']['protocol']['mean']==3.
    assert r['by_turn'][0]['mean']==4. and r['by_turn'][1]['mean']==9.
    assert r['excluded_special_tokens']==1
    assert [(p['trajectory_path'],p['turn_index']) for p in r['top_positions']]==[('a.json',1),('b.json',0)]
