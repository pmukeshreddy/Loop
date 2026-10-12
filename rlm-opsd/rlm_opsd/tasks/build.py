"""Release accepted candidates as the OPSD task pool, and load it answer-free."""
from collections import Counter
import json
from pathlib import Path
import shutil
import tempfile

from .decontam import HeldoutIndex, decontaminate
from .models import DOMAIN, SPLITS, Task, canonical, digest
from .store import Store, read_json
from .prepare import repo_ref


def _counts(rows, *keys):
    counts = Counter(tuple(r[k] for k in keys) for r in rows)
    return [dict(zip(keys, key), count=n) for key, n in sorted(counts.items())]


def _rejections(work):
    """Final rejections only: the last row per candidate that is still rejected (reopened ones excluded)."""
    path = Path(work) / 'rejections.jsonl'
    store = Store(work)
    latest = {}
    for line in (path.read_text().splitlines() if path.exists() else []):
        row = json.loads(line)
        latest[row['cid']] = row
    rows = [r for cid, r in latest.items() if store.status(cid) == 'rejected']
    by_code = Counter((r['stage'], r['code'].split(':')[0]) for r in rows)
    return dict(total=len(rows), by_stage_code=[dict(stage=s, code=c, count=n) for (s, c), n in sorted(by_code.items())],
                by_split=dict(Counter(r.get('split') for r in rows)),
                by_origin=dict(Counter(r.get('origin') for r in rows)))


def _write_pool(staging, tasks, store, extras):
    (staging / 'contexts').mkdir(parents=True)
    rows = []
    for task in sorted(tasks, key=lambda t: t.task_id):
        payload = canonical(task.context)
        relative = f'contexts/{digest(payload)}.json'
        if not (staging / relative).exists():
            (staging / relative).write_text(payload + '\n', encoding='utf-8')
        rows.append(task.manifest(relative))
        reference = staging / task.reference_path
        reference.mkdir(parents=True)
        source = store.candidates / task.task_id
        spec = store.read(task.task_id, 'spec.json')
        (reference / 'reference.json').write_text(json.dumps(dict(
            task_id=task.task_id, answer=task.answer, answer_type=task.answer_type,
            answer_format=task.answer_format, spec=spec, verification=task.verification,
            truth=store.read(task.task_id, 'truth.json'), practice=task.practice,
            review=extras[task.task_id]['review'], baseline=store.read(task.task_id, 'baseline.json'),
            suggestion=task.variation), indent=1, sort_keys=True) + '\n', encoding='utf-8')
        for name in ('reference.patch', 'oracle.py'):
            if (source / name).exists():
                shutil.copy(source / name, reference / name)
        for key in ('setup_patch', 'probe_patch', 'hidden_tests_patch'):
            if spec.get(key):
                (reference / f'{key.replace("_patch", "")}.patch').write_text(spec[key], encoding='utf-8')
        attempt = task.verification['attempt']
        shutil.copy(source / f'trajectory-{attempt}.json', reference / 'trajectory.json')
        if (source / 'logs').exists():
            shutil.copytree(source / 'logs', reference / 'logs')
    manifest = ''.join(canonical(row) + '\n' for row in rows)
    (staging / 'manifest.jsonl').write_text(manifest, encoding='utf-8')
    return rows, manifest


def build_pool(config, root, output_dir, *, verify_runs=1):
    """Release accepted tasks. With `verify_runs`, every task's executable ground truth is
    re-run on fresh checkouts first; tasks that do not reproduce are rejected and excluded."""
    root, output = Path(root), Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError('output directory must be empty; do not overwrite an existing task pool')
    work = root / config['work_dir']
    store = Store(work)
    run = read_json(work / 'run.json') or {}
    lock = read_json(work / 'sources.lock.json') or {}
    splits = read_json(work / 'splits.json')
    if not splits:
        raise ValueError('no repository split; run prepare and generate first')
    index_path = root / config['heldout']['index']
    heldout = HeldoutIndex.load(index_path) if index_path.exists() else HeldoutIndex()
    tasks, extras = [], {}
    for cid in store.ids():
        if store.status(cid) != 'accepted':
            continue
        accepted = store.read(cid, 'accepted.json')
        context = store.read(cid, 'context.json')
        repo = accepted['repo']
        if splits['assignment'][repo['name']] != accepted['split']:
            raise ValueError(f'{cid}: split differs from its repository assignment')
        provenance = dict(
            generator='agentinstruct-deepswe-v1', model=config['models']['model'],
            efforts=config['models']['effort'], skills=run.get('skills', {}),
            tree_sha256=lock.get(repo['name'], {}).get('tree_sha256'),
            documents=accepted['documents'], logs=accepted['logs'], origin=accepted['origin'],
            solver_harness_overrides=config.get('solver_harness_overrides') or {},
            manual_version='reference execution only; OPSD teacher manual unchanged')
        tasks.append(Task(
            task_id=cid, split=accepted['split'], family=accepted['family'], rlm_behaviors=accepted['rlm_behaviors'],
            behavior_rationale=accepted['behavior_rationale'], setting=accepted['setting'], query=accepted['query'],
            context=context, answer=accepted['answer'], answer_type=accepted['answer_type'],
            answer_format=accepted['answer_format'], size_bucket=accepted['size_bucket'], repo=repo,
            source=f"{repo['name']}@{repo['commit']}; {repo['license']}; generated task",
            source_refs=[repo_ref(repo['name'])], tags=accepted['tags'], domain=DOMAIN,
            parent_id=accepted['parent_id'], variation=accepted['variation'],
            practice=dict(intended=accepted['intended_behaviors'], **accepted['practice']),
            verification=accepted['verification'], reference_path=f'references/{cid}', provenance=provenance))
        extras[cid] = accepted
    kept, decontamination = decontaminate(tasks, heldout, **config['heldout']['decontamination'])
    output.parent.mkdir(parents=True, exist_ok=True)
    reverification = dict(runs=verify_runs, checked=0, failed=[])
    with tempfile.TemporaryDirectory(prefix='.tasks-build-', dir=output.parent) as temporary:
        staging = Path(temporary) / 'pool'
        rows, manifest = _write_pool(staging, kept, store, extras)
        if verify_runs and kept:
            import asyncio
            from .reverify import verify_pool
            result = asyncio.run(verify_pool(config, root, staging / 'manifest.jsonl', runs=verify_runs,
                                             log=lambda message: None))
            reverification.update(checked=len(kept), failed=result['failed'])
            failed = {f['task_id']: f for f in result['failed']}
            for cid, failure in failed.items():
                store.reject(cid, 'release', 'reverification_failed', f"{failure['code']}: {failure['detail']}")
            if failed:
                kept = [t for t in kept if t.task_id not in failed]
                shutil.rmtree(staging)
                rows, manifest = _write_pool(staging, kept, store, extras)
        report = dict(
            generated_total=len(store.ids()), accepted_total=len(tasks), written_total=len(rows),
            written_by_split=dict(Counter(r['split'] for r in rows)),
            released_grid=_counts(rows, 'split', 'family', 'size_bucket'),
            by_family=_counts(rows, 'split', 'family'), by_setting=_counts(rows, 'split', 'setting'),
            by_answer_type=_counts(rows, 'split', 'answer_type'),
            by_repository=[dict(split=s, repository=r, count=n) for (s, r), n in sorted(
                Counter((row['split'], row['repo']['name']) for row in rows).items())],
            behaviors=dict(Counter(b for r in rows for b in r['rlm_behaviors'])),
            variations=sum(1 for r in rows if r['parent_id']), reverification=reverification,
            rejections=_rejections(work), splits=splits, sources=lock, skills=run.get('skills', {}),
            decontamination=decontamination, config=config)
        report['manifest_sha256'] = digest(manifest)
        (staging / 'build-report.json').write_text(json.dumps(report, sort_keys=True, indent=2, default=str) + '\n',
                                                   encoding='utf-8')
        (staging / 'decontamination.json').write_text(json.dumps(decontamination, sort_keys=True, indent=2) + '\n',
                                                      encoding='utf-8')
        if output.exists():
            output.rmdir()  # only an empty user-selected output was accepted above
        staging.replace(output)
    return report


def _read_tasks(manifest_path):
    manifest = Path(manifest_path)
    seen = set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['task_id'] in seen:
            raise ValueError('duplicate manifest task ID')
        seen.add(row['task_id'])
        path = (manifest.parent / row['context_path']).resolve()
        if not path.is_relative_to(manifest.parent.resolve()):
            raise ValueError('context path escapes task pool')
        context = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(context, list) or not all(isinstance(x, str) for x in context):
            raise ValueError('invalid context type')
        if digest(canonical(context)) != row['context_sha256'] or sum(map(len, context)) != row['context_chars']:
            raise ValueError('context checksum or length mismatch')
        if row['context_format'] != 'list':
            raise ValueError('context format mismatch')
        yield Task.from_manifest(row, context)


def load_tasks(manifest_path, *, split, inspection_only=False):
    if split not in (*SPLITS, 'eval_heldout'):
        raise ValueError('select an explicit split')
    path = Path(manifest_path)
    if split != 'eval_heldout' and not inspection_only:
        report = json.loads((path.parent / 'build-report.json').read_text(encoding='utf-8'))
        if not report['decontamination']['coverage_complete']:
            raise ValueError('heldout coverage is incomplete; pool is inspection-only')
        if digest(path.read_text(encoding='utf-8')) != report['manifest_sha256']:
            raise ValueError('manifest changed after decontamination')
    for index, task in enumerate(_read_tasks(path)):
        if task.split != split:
            continue
        # Deliberately no answer, reference, verification or rationale in OPSD input.
        info = dict(task_id=task.task_id, family=task.family, domain=task.domain,
                    tags=task.tags, query=task.query, context=task.context)
        yield dict(example_id=index, prompt=[dict(role='user', content=task.query)], info=info)
