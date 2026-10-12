"""Atomic JSON state for resumable generation."""
import asyncio
import json
import os
from pathlib import Path
import time


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    temporary.replace(path)


def read_json(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.candidates = self.root / 'candidates'
        self.candidates.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def path(self, cid, name):
        return self.candidates / cid / name

    def read(self, cid, name):
        return read_json(self.path(cid, name))

    def write(self, cid, name, value):
        write_json(self.path(cid, name), value)

    def status(self, cid):
        return (self.read(cid, 'status.json') or {}).get('status', 'pending')

    def ids(self):
        return sorted(p.name for p in self.candidates.iterdir() if (p / 'meta.json').exists())

    def log(self, name, row):
        with (self.root / name).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(time=round(time.time(), 3), **row), sort_keys=True, default=str) + '\n')

    def reject(self, cid, stage, code, detail=''):
        meta = self.read(cid, 'meta.json') or {}
        row = dict(cid=cid, repo=meta.get('repo'), split=meta.get('split'), origin=meta.get('origin'),
                   parent_id=meta.get('parent_id'), stage=stage, code=code, detail=str(detail)[:2000])
        self.write(cid, 'status.json', dict(status='rejected', stage=stage, code=code, detail=str(detail)[:2000]))
        self.log('rejections.jsonl', row)

    def accept(self, cid):
        self.write(cid, 'status.json', dict(status='accepted'))
        self.log('events.jsonl', dict(cid=cid, event='accepted'))




# Stage outputs recomputed when a rejection is reopened, by rejecting stage.
REOPEN_OUTPUTS = {
    'start': ('error.json',),  # infrastructure errors before any stage produced output
    'solve': ('verification.json',),  # stored solves are re-verified before any new attempt
    'practice': ('practice.json', 'review.json'),
    'review': ('review.json',),
    'release': (),  # release-time re-verification; rerun by the next build
}


def reopen(work_dir, codes):
    """Return candidates rejected with `codes` to pending after the check that rejected them was fixed.

    Only stages whose outputs can be recomputed without new model work (practice,
    review) are reopened; the reopening is logged so the release report counts
    only final rejections.
    """
    store = Store(work_dir)
    reopened = []
    for cid in store.ids():
        state = store.read(cid, 'status.json') or {}
        if state.get('status') != 'rejected' or state.get('code') not in codes:
            continue
        if state.get('stage') not in REOPEN_OUTPUTS:
            raise ValueError(f'{cid}: stage {state.get("stage")} cannot be reopened without regenerating work')
        for name in ('status.json',) + REOPEN_OUTPUTS[state['stage']]:
            store.path(cid, name).unlink(missing_ok=True)
        store.log('events.jsonl', dict(cid=cid, event='reopened', code=state['code'], stage=state['stage']))
        reopened.append(cid)
    return reopened
