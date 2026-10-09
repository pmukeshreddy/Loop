import copy
import pytest


def settings(**changes):
    from rlm_opsd.eval.monitor_config import ExitRules
    return ExitRules(**{**dict(behavior_tolerance=.125,min_known=1,max_unknown_fraction=0.,
                              retention_tolerance=.125),**changes})


def evidence():
    rows=[dict(phase=phase,metric='D15',dimension='overall',group='all',category='',
               value=value,known=8,unknown=0,trajectory_paths=[phase+'.json'])
          for phase,value in [('before',0.),('teacher',1.),('after',.875)]]
    return dict(behavior=rows,retention=dict(before=.75,after=.625,count=8))


def decide(data=None,**changes):
    from rlm_opsd.eval.exit import evaluate_exit
    return evaluate_exit(evidence() if data is None else data,settings(**changes))


def test_both_exit_conditions_are_inclusive_and_conjunctive():
    assert decide()['status']=='passed'
    for changes in ({'behavior_tolerance':.124},{'retention_tolerance':.124}):
        assert decide(**changes)['status']=='failed'
    assert decide()['behavior'][0]['gap']==.125


@pytest.mark.parametrize('fault', ['missing_after','missing_teacher','unknown','null','retention','empty','extra_after'])
def test_missing_or_unknown_evidence_is_inconclusive(fault):
    data=evidence()
    if fault=='missing_after':data['behavior'].pop()
    elif fault=='missing_teacher':data['behavior'].pop(1)
    elif fault=='extra_after':data['behavior'].append({**data['behavior'][-1],'group':'new','dimension':'family'})
    elif fault=='unknown':data['behavior'][-1]['unknown']=1
    elif fault=='null':data['behavior'][-1]['value']=None
    elif fault=='retention':data['retention']['after']=None
    elif fault=='empty':data['behavior']=[]
    assert decide(data)['status']=='inconclusive'


def test_category_and_group_comparisons_cannot_be_hidden_by_overall_mean():
    data=evidence()
    data['behavior'] += [dict(phase=p,metric='D19',category='direct_read',dimension='family',group='small',
                              value=v,known=1,unknown=0,trajectory_paths=[]) for p,v in [('teacher',1.),('after',0.)]]
    assert decide(data)['status']=='failed'
    data=evidence();data['retention']['after']=1.
    assert decide(data)['status']=='passed'  # Improvement is not loss of capability.


def test_exit_settings_have_no_invented_defaults():
    from rlm_opsd.eval.monitor_config import ExitRules
    with pytest.raises(ValueError):ExitRules()
    for changes in ({'behavior_tolerance':None},{'min_known':0},{'max_unknown_fraction':1.1},
                    {'retention_tolerance':True},{'retention_tolerance':float('nan')}):
        with pytest.raises(ValueError):settings(**changes)


def test_duplicate_behavior_evidence_is_rejected():
    data=evidence();data['behavior'].append(copy.deepcopy(data['behavior'][-1]))
    with pytest.raises(ValueError):decide(data)


def saved_evidence(tmp_path):
    """Synthetic schema contract only; not operational model evidence."""
    import json
    from pathlib import Path
    from rlm_opsd.detectors import DetectorConfig,analyze_trajectory,aggregate_behavior
    from rlm_opsd.eval.gate import write_json
    from rlm_opsd.eval.monitor_reports import seal_evidence,summarize_divergence
    root=tmp_path/'evidence';root.mkdir()
    fixture=Path(__file__).parent/'fixtures'/'detectors'
    config=DetectorConfig.from_yaml(fixture/'fixture-config.yaml')
    records=[];requests=[]
    for phase in ('before','teacher','after'):
        raw=json.loads((fixture/'before.json').read_text());raw['task_id']='dev-one'
        raw['prompt_variant']='teacher' if phase=='teacher' else 'student'
        write_json(root/(phase+'.json'),raw)
        records.append(dict(phase=phase,analysis=analyze_trajectory(raw,config),trajectory_path=phase+'.json',task_success=False))
        requests.append(dict(phase=phase,task_id='dev-one',role='student' if phase=='after' else 'base',status='completed'))
    for name,rows in [('records',records),('requests',requests)]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    turns=[dict(turn_index=0,text='X',offsets=[[0,1]],values=[1.],trajectory_path=str(root/'after.json'))]
    write_json(root/'token-scores.json',turns)
    for name in ('behavior.csv','behavior.md','monitor.md','divergence.csv'):(root/name).write_text('schema test artifact\n')
    write_json(root/'detectors.json',config.model_dump(mode='json'))
    write_json(root/'answers.json',{'dev-one':['wrong','exact']})
    provenance=dict(checkpoint_sha256='1'*64,dev_task_ids=['dev-one'])
    write_json(root/'run.json',dict(status='completed',kind='pretrained_model_evaluation',provenance=provenance,
        config={'run_label':'SCHEMA CONTRACT TEST','kl_top_k':1}))
    metrics=dict(behavior=aggregate_behavior([{**r,'trajectory_path':str(root/r['trajectory_path'])} for r in records]),
        divergence=summarize_divergence(turns,top_k=1))
    write_json(root/'metrics.json',metrics)
    write_json(root/'monitor.json',dict(status='completed',kind='pretrained_model_evaluation',errors=[],provenance=provenance,
        evidence=seal_evidence(root)))
    return root


@pytest.mark.parametrize('fault',[None,'hash','checkpoint','missing_phase','escape','fixture','summary','request'])
def test_exit_validates_complete_bound_behavior_evidence(tmp_path,fault):
    import json
    from rlm_opsd.eval.exit import load_evaluation
    from rlm_opsd.eval.gate import write_json
    from rlm_opsd.eval.monitor_reports import seal_evidence
    root=saved_evidence(tmp_path);expected='1'*64
    result=json.loads((root/'monitor.json').read_text())
    if fault=='checkpoint':expected='2'*64
    elif fault=='hash':(root/'behavior.csv').write_text('modified')
    elif fault=='escape':result['evidence']['../escape.json']='0'*64
    elif fault=='fixture':result['kind']='cpu_tensor_fixture'
    elif fault in ('missing_phase','summary','request'):
        name={'missing_phase':'records.jsonl','summary':'metrics.json','request':'requests.jsonl'}[fault]
        path=root/name
        if fault=='summary':
            metrics=json.loads(path.read_text());metrics['behavior'][0]['value']=.123;write_json(path,metrics)
        else:
            rows=[json.loads(line) for line in path.read_text().splitlines()];rows.pop()
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        result['evidence']=seal_evidence(root)
    write_json(root/'monitor.json',result)
    if fault:
        with pytest.raises((ValueError,FileNotFoundError)):load_evaluation(root,expected)
    else:assert load_evaluation(root,expected)['behavior']


def test_decimal_rate_boundaries_are_inclusive_but_larger_drops_fail():
    data=evidence()
    data['behavior'][1]['value']=.8;data['behavior'][2]['value']=.7
    data['retention'].update(before=.8,after=.7)
    assert decide(data,behavior_tolerance=.1,retention_tolerance=.1)['status']=='passed'
    data['behavior'][2]['value']=.7-1e-10
    assert decide(data,behavior_tolerance=.1,retention_tolerance=.1)['status']=='failed'
    data['behavior'][2]['value']=.7
    data['retention']['after']=.7-1e-10
    assert decide(data,behavior_tolerance=.1,retention_tolerance=.1)['status']=='failed'
