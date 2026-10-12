"""Progress summary of a generation work directory; reads state only."""
from collections import Counter
import json
from pathlib import Path

from .store import Store, read_json


def status(config, root):
    work = Path(root) / config['work_dir']
    store = Store(work)
    rows = []
    for cid in store.ids():
        meta = store.read(cid, 'meta.json')
        state = store.read(cid, 'status.json') or dict(
            status='pending' if store.read(cid, 'spec.json') is not None else 'drafting')
        accepted = store.read(cid, 'accepted.json') if state['status'] == 'accepted' else None
        rows.append(dict(meta, status=state['status'], code=state.get('code'), stage=state.get('stage'),
                         family=accepted['family'] if accepted else None))
    usage = work / 'usage.jsonl'
    calls = [json.loads(line) for line in usage.read_text().splitlines()] if usage.exists() else []
    return dict(
        candidates=len(rows),
        by_status=dict(Counter(r['status'] for r in rows)),
        accepted_by_split=dict(Counter(r['split'] for r in rows if r['status'] == 'accepted')),
        accepted_by_family=dict(Counter(r['family'] for r in rows if r['status'] == 'accepted')),
        accepted_by_repo=dict(Counter(r['repo'] for r in rows if r['status'] == 'accepted')),
        rejected_by_code=dict(Counter(r['code'].split(':')[0] for r in rows if r['status'] == 'rejected').most_common()),
        model_calls=len(calls), input_tokens=sum(c['input_tokens'] for c in calls),
        output_tokens=sum(c['output_tokens'] for c in calls),
        splits=(read_json(work / 'splits.json') or {}).get('assignment'))
