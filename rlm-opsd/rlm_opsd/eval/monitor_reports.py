"""Source-linked monitoring summaries, readable samples and evidence inventory."""
import csv
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote

from rlm_opsd.detectors.categories import CATEGORIES,summarize_token_divergence
from .preflight import sha256


def _stats(values):
    total=math.fsum(values)
    return dict(count=len(values),sum=total,mean=total/len(values) if values else None)


def summarize_divergence(turns,*,top_k):
    categories={c:[] for c in CATEGORIES};by_turn={};all_values=[];top=[];excluded=0
    for turn in turns:
        summary=summarize_token_divergence([turn],metric_kind='full_kl',top_k=len(turn['values']))
        excluded+=summary['excluded_special_tokens']
        for position in summary['top_positions']:
            categories[position['category']].append(position['value'])
            top.append({**position,'trajectory_path':turn['trajectory_path']})
        all_values.extend(turn['values']);by_turn.setdefault(turn['turn_index'],[]).extend(turn['values'])
    top.sort(key=lambda p:(-p['value'],p['trajectory_path'],p['turn_index'],p['token_index']))
    return dict(metric_kind='full_kl',direction='KL(teacher || student)',log_base='e',
        overall=_stats(all_values),by_category={c:_stats(v) for c,v in categories.items()},
        by_turn=[dict(turn_index=i,**_stats(v)) for i,v in sorted(by_turn.items())],
        excluded_special_tokens=excluded,top_positions=top[:top_k],
        trajectory_paths=sorted({t['trajectory_path'] for t in turns}))


def seal_evidence(output):
    output=Path(output)
    return {str(p.relative_to(output)):sha256(p) for p in sorted(output.rglob('*'))
            if p.is_file() and p.name not in ('monitor.json','rendezvous')}


def _link(path,output):
    import os
    return quote(os.path.relpath(path,output),safe='/')


def write_monitor_reports(output,config,records,result):
    lines=['# OPSD monitoring','',config.run_label,'',f"Status: **{result['status']}**",
        '',f"Checkpoint step: {config.checkpoint_step}. [Run settings and identity](run.json).",
        '', '[Behavior](behavior.md) · [Behavior CSV](behavior.csv) · [Requests](requests.jsonl)',
        '', 'Endpoint weight identity is operator-declared. Teacher scoring is local.',
        'Correctness is measured only; this command performs no optimization.','']
    metric_path=output/'metrics.json'
    if metric_path.exists():
        metrics=json.loads(metric_path.read_text());d=metrics['divergence']
        lines += [f"Teacher KL(T||S): {d['overall']['mean']} over {d['overall']['count']} root targets. "
                  '[Token scores](token-scores.json) · [Divergence CSV](divergence.csv).',
            '', 'Overall KL and turn means include all selected root targets. Category means and top text positions exclude special-token offsets.',
            'Full decoded completions, including reasoning, supply category text. Scored IDs always come from the rollout.',
            '', '| Category / turn | Mean KL | Count | Evidence |', '| --- | ---: | ---: | --- |']
        csv_rows=[dict(group='overall',label='all',**d['overall'])]
        for label,value in d['by_category'].items():csv_rows.append(dict(group='category',label=label,**value))
        for value in d['by_turn']:csv_rows.append(dict(group='turn',label=value['turn_index'],**{k:value[k] for k in ('count','sum','mean')}))
        for row in csv_rows:lines.append(f"| {row['group']} / {row['label']} | {row['mean']} | {row['count']} | [scores](token-scores.json) |")
        with (output/'divergence.csv').open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=['group','label','count','sum','mean','evidence'])
            writer.writeheader();writer.writerows({**r,'evidence':'token-scores.json'} for r in csv_rows)
        lines+=['','Highest-KL text positions:','']
        for p in d['top_positions']:
            lines += [f"- KL {p['value']}, turn {p['turn_index']}, token {p['token_index']}: "
                      f"[trajectory]({_link(p['trajectory_path'],output)})",'',
                      '    '+repr(p['context']),'']
    else:lines+=['Divergence: not completed. Partial trajectories and requests are preserved.']
    (output/'monitor.md').write_text('\n'.join(lines)+'\n')
    selected={}
    for record in records:
        if record['phase']!='after':continue
        family=record['analysis']['family'];count=selected.get(family,0)
        if count>=config.review_per_family:continue
        selected[family]=count+1
        path=Path(record['trajectory_path']);raw=json.loads(path.read_text())
        # Family comes from the closed task schema; still avoid path traversal.
        if Path(family).name!=family or family in ('.','..'):raise ValueError('unsafe review family')
        directory=output/'review'/f'step_{config.checkpoint_step}'/family;directory.mkdir(parents=True,exist_ok=True)
        name=hashlib.sha256(raw['task_id'].encode()).hexdigest()[:16]+'.md'
        text=[f"# {raw['task_id']}",'',f"[Source trajectory]({_link(path,directory)})",'']
        for i,turn in enumerate(raw['turns']):
            text += [f'## Turn {i}','', 'Assistant:', '', *['    '+line for line in turn['assistant_text'].splitlines()],
                     '', 'Observation:', '', *['    '+line for line in turn['stdout_truncated'].splitlines()], '']
        text+=['Final:', '', '    '+json.dumps(raw['final'],ensure_ascii=False)]
        (directory/name).write_text('\n'.join(text)+'\n')
