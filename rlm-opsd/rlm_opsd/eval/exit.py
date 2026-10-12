"""Conjunctive SPEC §8 decisions from measured monitoring evidence."""
import math


def _fraction(value):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=1


def _within_limit(value,limit):
    # Inputs are fractions in [0,1]. Allow only subtraction roundoff, not a
    # statistical tolerance: four binary64 ULPs at 1 (~8.9e-16).
    return value<=limit or math.isclose(value,limit,rel_tol=0.,abs_tol=4*math.ulp(1.))


def evaluate_exit(metrics, rules):
    indexed={}
    for row in metrics['behavior']:
        if row['phase'] not in ('teacher','after'):continue
        if row['metric'] not in {'task_tag_match',*[f'D{i}' for i in range(1,20)]}:continue
        key=(row['dimension'],row['group'],row['metric'],row.get('category',''))
        pair=indexed.setdefault(key,{})
        if row['phase'] in pair:raise ValueError('duplicate behavior metric')
        pair[row['phase']]=row
    comparisons=[]
    for key,pair in sorted(indexed.items()):
        enough=len(pair)==2
        for row in pair.values():
            known,unknown=row['known'],row['unknown']
            enough &= (type(known) is int and type(unknown) is int and known>=rules.min_known
                and unknown>=0 and unknown/(known+unknown)<=rules.max_unknown_fraction
                and _fraction(row['value']))
        gap=abs(pair['after']['value']-pair['teacher']['value']) if enough else None
        comparisons.append(dict(dimension=key[0],group=key[1],metric=key[2],category=key[3],
            gap=gap,status='inconclusive' if gap is None else 'passed' if _within_limit(gap,rules.behavior_tolerance) else 'failed',
            trajectory_paths=sorted({p for row in pair.values() for p in row['trajectory_paths']})))
    retention=metrics.get('retention',{})
    drop=None
    if (retention.get('count',0)>0 and _fraction(retention.get('before')) and _fraction(retention.get('after'))):
        drop=retention['before']-retention['after']
    retention_status='inconclusive' if drop is None else 'passed' if _within_limit(drop,rules.retention_tolerance) else 'failed'
    statuses=[r['status'] for r in comparisons] or ['inconclusive']
    statuses += [retention_status]
    return dict(status='failed' if 'failed' in statuses else 'inconclusive' if 'inconclusive' in statuses else 'passed',
        behavior=comparisons,retention=dict(status=retention_status,drop=drop),
        rules=rules.model_dump())


def load_evaluation(directory,expected_checkpoint_sha256):
    """Accept complete, unmodified real monitoring runs only; never fixture evidence."""
    import json
    from pathlib import Path
    from .preflight import sha256
    from rlm_opsd.training.runner import contained
    root=Path(directory).resolve()
    result=json.loads((root/'monitor.json').read_text())
    if result.get('status')!='completed' or result.get('kind')!='pretrained_model_evaluation' or result.get('errors'):
        raise ValueError('a completed real evaluation is required; fixture/error runs cannot authorize exit')
    inventory=result.get('evidence',{})
    required={'answers.json','run.json','metrics.json','detectors.json','records.jsonl','requests.jsonl','token-scores.json',
              'behavior.csv','behavior.md','monitor.md','divergence.csv'}
    if not required<=inventory.keys():raise ValueError('evaluation evidence inventory is incomplete')
    for relative,digest in inventory.items():
        if sha256(contained(root,relative))!=digest:raise ValueError('evaluation evidence hash differs')
    run=json.loads((root/'run.json').read_text())
    if (run.get('status')!='completed' or run.get('kind')!='pretrained_model_evaluation'
            or any(word in run.get('config',{}).get('run_label','').lower() for word in ('fixture','synthetic'))):
        raise ValueError('real evaluation provenance is required')
    provenance=run['provenance']
    if (provenance!=result.get('provenance') or provenance.get('checkpoint_sha256')!=expected_checkpoint_sha256):
        raise ValueError('evaluation checkpoint/provenance differs')
    records=[json.loads(line) for line in (root/'records.jsonl').read_text().splitlines()]
    expected={(p,i) for p in ('before','teacher','after') for i in provenance['dev_task_ids']}
    actual=[(r['phase'],r['analysis']['task_id']) for r in records]
    if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('evaluation dev coverage is incomplete')
    for r in records:
        if r['trajectory_path'] not in inventory:raise ValueError('unhashed trajectory evidence')
        raw=json.loads(contained(root,r['trajectory_path']).read_text())
        if raw['task_id']!=r['analysis']['task_id'] or raw['prompt_variant']!=('teacher' if r['phase']=='teacher' else 'student'):
            raise ValueError('evaluation trajectory identity differs')
    requests=[json.loads(line) for line in (root/'requests.jsonl').read_text().splitlines()]
    if not requests or any(r.get('status')!='completed' for r in requests):raise ValueError('generation evidence failed or missing')
    pairs={(r.get('phase'),r.get('task_id')) for r in requests if r.get('role') in ('base','student')}
    if not expected<=pairs:raise ValueError('generation evidence does not cover dev phases')
    from rlm_opsd.detectors import DetectorConfig,analyze_trajectory,aggregate_behavior
    from .metrics import score_trajectory, task_success
    from .monitor_reports import summarize_divergence
    detectors=DetectorConfig.model_validate(json.loads((root/'detectors.json').read_text()))
    answers=json.loads((root/'answers.json').read_text())
    recomputed=[]
    for record in records:
        path=contained(root,record['trajectory_path']);raw=json.loads(path.read_text())
        analysis=analyze_trajectory(raw,detectors)
        success=task_success(score_trajectory(raw,*answers[raw['task_id']]))
        if json.loads(json.dumps(analysis))!=record['analysis'] or success!=record.get('task_success'):
            raise ValueError('saved behavior analysis differs from trajectory evidence')
        recomputed.append(dict(phase=record['phase'],trajectory_path=str(path),analysis=analysis,
                               **({} if success is None else dict(task_success=success))))
    turns=json.loads((root/'token-scores.json').read_text())
    after_paths={str(contained(root,r['trajectory_path'])) for r in records if r['phase']=='after'}
    if not turns or {t['trajectory_path'] for t in turns}!=after_paths:raise ValueError('KL coverage differs')
    measured=dict(behavior=aggregate_behavior(recomputed),
        divergence=summarize_divergence(turns,top_k=run['config']['kl_top_k']))
    metrics=json.loads((root/'metrics.json').read_text())
    if metrics!=measured:raise ValueError('monitoring summary differs from source evidence')
    return measured


def prepare_exit(config):
    """No-network prerequisites; behavior evaluation itself needs no retention set."""
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from .monitor_config import MonitorConfig
    from .retention import load_retention
    from .preflight import sha256
    from rlm_opsd.training.config import OpsdConfig
    from rlm_opsd.training.runner import verify_gate
    retention=load_retention(config.retention_path)
    metrics=load_evaluation(config.evaluation_dir,config.expected_checkpoint_sha256)
    run=json.loads((config.evaluation_dir/'run.json').read_text())
    values=run['config'].copy()
    for key in ('training_config','checkpoint'):values[key]=Path(values[key])
    monitor=MonitorConfig.model_validate(values)
    provenance=run['provenance']
    if (sha256(monitor.training_config)!=provenance['training_config_sha256']
            or sha256(monitor.checkpoint)!=config.expected_checkpoint_sha256):
        raise ValueError('training settings or checkpoint changed since behavior evaluation')
    training=OpsdConfig.from_toml(monitor.training_config)
    gate,plan=verify_gate(training)
    # This field describes the operator-declared identity limitation, not bytes
    # or a model identifier; monitor extends its wording to include the adapter.
    if any(provenance.get(k)!=v for k,v in plan.provenance.items() if k!='endpoint_identity'):
        raise ValueError('behavior inputs or gate settings changed since evaluation')
    if monitor.student_endpoint.api_key_var and not os.environ.get(monitor.student_endpoint.api_key_var):
        raise ValueError('student endpoint API-key environment variable is missing')
    return SimpleNamespace(metrics=metrics,monitor=monitor,gate=gate,prompts=plan.prompt_config,retention=retention)


def check_exit(path):
    from .monitor_config import ExitConfig
    from .preflight import safe_error
    try:
        prepare_exit(ExitConfig.from_yaml(path))
        return dict(status='ready',blockers=[],model_requests_sent=False)
    except Exception as exc:
        return dict(status='not_run',blockers=[safe_error(exc)],model_requests_sent=False)


async def run_exit(config,output_dir):
    import asyncio
    import os
    from pathlib import Path
    from urllib.parse import quote
    from .gate import write_json
    from .preflight import sha256
    from .retention import collect_retention
    from .monitor_reports import seal_evidence
    output=Path(output_dir).resolve()
    if output.exists():raise FileExistsError('exit output already exists')
    plan=prepare_exit(config)
    output.mkdir(parents=True,exist_ok=False)
    result=dict(status='error',evaluation_dir=str(config.evaluation_dir),
        evaluation_sha256=sha256(config.evaluation_dir/'monitor.json'),
        expected_checkpoint_sha256=config.expected_checkpoint_sha256,
        retention_sha256=sha256(config.retention_path),config=config.model_dump(mode='json'))
    write_json(output/'retention-inputs.json',plan.retention)
    (output/'requests.jsonl').touch();cancelled=None
    try:
        scores=await collect_retention(config,plan,output)
        result.update(evaluate_exit({**plan.metrics,'retention':scores},config.rules),retention_scores=scores)
    except (Exception,asyncio.CancelledError) as exc:
        result.update(status='error',error_type=type(exc).__name__)
        if isinstance(exc,asyncio.CancelledError):cancelled=exc
    link=quote(os.path.relpath(config.evaluation_dir/'monitor.json',output),safe='/')
    lines=['# OPSD exit check','',f"Status: **{result['status']}**",'',
        f'[Behavior evidence]({link}) · [Decision](exit.json) · [Retention requests](requests.jsonl)',
        '', 'Exit requires both behavior agreement and retention. No GRPO-pool criterion is evaluated.','']
    if 'retention' in result:
        lines += [f"Retention drop: {result['retention']['drop']}; {result['retention']['status']}. [Paired responses](retention.jsonl).",
            '', '| Metric / group | Absolute gap | Status |', '| --- | ---: | --- |']
        for row in result['behavior']:
            label=' / '.join(str(row[k]).replace('|','\\|') for k in ('dimension','group','metric','category'))
            lines.append(f"| {label} | {row['gap']} | {row['status']} |")
    else:lines+=['Retention: not completed. No exit decision was made.']
    (output/'exit.md').write_text('\n'.join(lines)+'\n')
    result['evidence']=seal_evidence(output)
    write_json(output/'exit.json',result)
    if cancelled:raise cancelled
    return result
