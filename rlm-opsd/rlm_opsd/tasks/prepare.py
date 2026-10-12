"""Pre-generation stage: pin sources, record baselines, split repositories, index held-out data.

Splits are assigned here, before any task exists, and never recomputed: a
repository and every task or variation derived from it share one split.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import random
import tempfile
import urllib.request

from .decontam import HeldoutIndex, HeldoutRecord
from .models import SPLITS, digest, normalized
from .store import read_json, write_json
from .repos import RepoSpec, Workspace, inventory, run_tests, select_documents


def checked_source(source, *, root, download=False):
    path = Path(root) / source['path']
    if not path.exists():
        if not download:
            raise ValueError(f'missing source {path}; run tasks prepare')
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(source['url'], timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            raise ValueError(f'download checksum mismatch: {path}')
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError(f'source checksum mismatch: {path}')
    return path


def repo_ref(name):
    """Repository identity shared by generated tasks and DeepSWE held-out records."""
    name = name.lower()
    return dict(dataset='github', revision='repository', item_id=name, sha256=digest(normalized(name)))


def deepswe_records(manifest_path, tasks_dir):
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    records = []
    for task in manifest['tasks']:
        instruction = Path(tasks_dir) / task['task_id'] / 'instruction.md'
        query = instruction.read_text(encoding='utf-8') if instruction.exists() else task['display_description']
        records.append(HeldoutRecord(benchmark='deepswe', task_id=task['task_id'], query=query,
                                     source_refs=[repo_ref(task['repo'])]))
    return records, hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()


def excluded_repositories(config, root):
    manifest = json.loads((Path(root) / config['heldout']['deepswe_manifest']).read_text(encoding='utf-8'))
    return {t['repo'].lower() for t in manifest['tasks']}


def build_heldout_index(config, root):
    held = config['heldout']
    records, coverage = [], {}
    deepswe, manifest_sha = deepswe_records(Path(root) / held['deepswe_manifest'], Path(root) / held['deepswe_tasks_dir'])
    records += deepswe
    coverage['deepswe'] = dict(complete=True, revision=manifest_sha, record_count=len(deepswe),
                               source_sha256=manifest_sha, license='Apache-2.0 (task specs); upstream licenses vary',
                               reason='complete local DeepSWE-113 manifest; repository-level exclusion')
    for source in held.get('question_sources', []):
        path = checked_source(source, root=root, download=True)
        rows = json.loads(path.read_text(encoding='utf-8'))
        for row in rows:
            records.append(HeldoutRecord(benchmark=source['benchmark'], task_id=str(row['id']),
                                         query=row['question'], source_refs=[]))
        coverage[source['benchmark']] = dict(complete=False, revision=source['revision'], record_count=len(rows),
                                             source_sha256=source['sha256'], license=source['license'],
                                             reason='queries only; context/source coverage missing')
    for source in held.get('snapshots', []):
        from .heldout import load_heldout_snapshot
        path = checked_source(source, root=root)
        imported = [HeldoutRecord(source['benchmark'], task.task_id, task.query, task.source_refs)
                    for task in load_heldout_snapshot(path, benchmark=source['benchmark'],
                                                      revision=source['revision'], license=source['license'])]
        if not imported:
            raise ValueError(f'no matching heldout tasks in {path}')
        records = [record for record in records if record.benchmark != source['benchmark']]
        records.extend(imported)
        coverage[source['benchmark']] = dict(complete=source.get('complete', False), revision=source['revision'],
                                             record_count=len(imported), source_sha256=source['sha256'],
                                             license=source['license'],
                                             reason='complete reserved snapshot' if source.get('complete') else 'partial snapshot')
    index = HeldoutIndex(records=records, coverage=coverage)
    path = Path(root) / held['index']
    path.parent.mkdir(parents=True, exist_ok=True)
    index.write(path)
    return index


def assign_splits(sizes, *, seed, dev_count):
    """Stratify repositories by context size; draw one dev repository per stratum."""
    if not 0 < dev_count < len(sizes):
        raise ValueError('dev_behavior_repositories must leave at least one train repository')
    ordered = sorted(sizes, key=lambda name: (sizes[name], name))
    rng = random.Random(f'{seed}:repository-split')
    assignment = {name: 'train' for name in ordered}
    for stratum in range(dev_count):
        members = ordered[stratum * len(ordered) // dev_count:(stratum + 1) * len(ordered) // dev_count]
        assignment[rng.choice(members)] = 'dev_behavior'
    return assignment


async def _baseline(workspace, runs, timeout_s):
    results = []
    for _ in range(runs):
        with tempfile.TemporaryDirectory(prefix='rlm-base-') as scratch:
            checkout = workspace.checkout(Path(scratch) / 'clean')
            results.append(await run_tests(workspace, checkout, timeout_s=timeout_s))
    ids = set().union(*(set(r.outcomes) for r in results))
    flaky = sorted(i for i in ids if len({r.outcomes.get(i) for r in results}) > 1)
    stable_passing = sorted(i for i in ids if i not in flaky and all(
        r.outcomes.get(i) in ('passed', 'xfailed') for r in results))
    failing = sorted(i for i in ids if i not in flaky and all(r.outcomes.get(i) in ('failed', 'error') for r in results))
    return dict(stable_passing=stable_passing, failing=failing, flaky=flaky, runs=runs,
                durations_s=[round(r.duration_s, 2) for r in results], log_tail=results[0].log[-3000:])


async def prepare_sources(config, root, *, log=print):
    root = Path(root)
    work = root / config['work_dir']
    sources = root / config['sources_dir']
    excluded = excluded_repositories(config, root)
    specs = [RepoSpec.from_config(r) for r in config['repositories']]
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise ValueError('duplicate repository entries')
    blocked = [s.name for s in specs if s.name.lower() in excluded]
    if blocked:
        raise ValueError(f'repositories reserved by DeepSWE-113 evaluation cannot be sources: {blocked}')
    lock, sizes = {}, {}
    semaphore = asyncio.Semaphore(config['generation']['test_concurrency'])

    async def one(spec):
        workspace = Workspace(spec, sources, config['python'])
        await asyncio.to_thread(workspace.ensure_clone)
        tree_sha, files = await asyncio.to_thread(workspace.ensure_tree)
        freeze = await asyncio.to_thread(workspace.ensure_venv)
        path = work / 'repos' / spec.slug / 'baseline.json'
        baseline = read_json(path)
        if baseline is None or baseline.get('commit') != spec.commit:
            async with semaphore:
                baseline = await _baseline(workspace, config['generation']['stability_runs'],
                                           config['generation']['test_timeout_s'])
            baseline['commit'] = spec.commit
            write_json(path, baseline)
        if not baseline['stable_passing']:
            raise ValueError(f'{spec.name}: no stable passing tests at the pinned commit')
        documents = inventory(spec, workspace.tree, exclude=config['context']['exclude'],
                              max_file_chars=config['context']['max_file_chars'])
        chosen = select_documents(documents, scope='repository', max_chars=config['context']['max_chars'],
                                  max_documents=config['context']['max_documents'])
        sizes[spec.name] = sum(len(d.text) for d in chosen)
        lock[spec.name] = dict(url=spec.url, ref=spec.ref, commit=spec.commit, license=spec.license,
                               tree_sha256=tree_sha, tree_files=files, python=config['python'],
                               test_deps=list(spec.test_deps), environment=freeze,
                               baseline=dict(passing=len(baseline['stable_passing']), failing=len(baseline['failing']),
                                             flaky=len(baseline['flaky']), durations_s=baseline['durations_s']),
                               repository_context_chars=sizes[spec.name])
        log(f'[prepare] {spec.name}: {len(baseline["stable_passing"])} stable passing tests, '
            f'{sizes[spec.name]} context chars')

    await asyncio.gather(*(one(spec) for spec in specs))
    write_json(work / 'sources.lock.json', dict(sorted(lock.items())))
    splits_path = work / 'splits.json'
    existing = read_json(splits_path)
    if existing is None:
        assignment = assign_splits(sizes, seed=config['seed'], dev_count=config['splits']['dev_behavior_repositories'])
        write_json(splits_path, dict(assignment=dict(sorted(assignment.items())), seed=config['seed'],
                                     method='size-stratified seeded draw before generation',
                                     sizes=dict(sorted(sizes.items()))))
    elif set(existing['assignment']) != set(names):
        raise ValueError('repository list changed after splits were fixed; start a new work_dir to re-split')
    index = build_heldout_index(config, root)
    splits = read_json(splits_path)['assignment']
    return dict(repositories=len(specs), splits={s: sorted(n for n, v in splits.items() if v == s) for s in SPLITS},
                heldout_records=len(index.records), missing_benchmarks=index.missing())
