"""Re-run executable verification for a released pool; no model requests."""
import asyncio
import json
from pathlib import Path
import tempfile

from .analysis import diff_symbols
from .materialize import FAIL, PASS, Rejected, base_id, stable
from .models import CandidateSpec
from .repos import RepoSpec, Workspace, apply_patch, run_tests
from .store import read_json
from .verify import normalize, matches, run_oracle, verify_patch


async def _state_runs(workspace, spec, runs, timeout):
    results = []
    with tempfile.TemporaryDirectory(prefix='rlm-reverify-') as scratch:
        checkout = workspace.checkout(Path(scratch) / 'state')
        if spec.setup_patch:
            ok, message = await apply_patch(checkout, spec.setup_patch)
            if not ok:
                raise Rejected('setup_patch_does_not_apply', message)
        for _ in range(runs):
            results.append(await run_tests(workspace, checkout, timeout_s=timeout))
        from .repos import patch_files
        symbols = diff_symbols(
            (p, (workspace.tree / p).read_text() if (workspace.tree / p).exists() else None, (checkout / p).read_text())
            for p in patch_files(spec.setup_patch)) if spec.setup_patch else []
    return results, symbols


async def verify_task(row, reference, workspace, baseline, config, lock, runs):
    spec = CandidateSpec.model_validate(reference['spec'])
    timeout = config['generation']['test_timeout_s']
    base_pass = set(baseline['stable_passing'])
    async with lock:
        state, symbols = await _state_runs(workspace, spec, runs, timeout)
    p2p = stable(state, lambda o: o in PASS) & base_pass
    kind, stored = row['answer_type'], reference['verification']
    if kind == 'patch':
        f2p = sorted(stable(state, lambda o: o in FAIL) & base_pass) if spec.setup_patch else []
        if f2p != sorted(stored['fail_to_pass']):
            raise Rejected('fail_to_pass_changed', f'{len(f2p)} vs {len(stored["fail_to_pass"])}')
        record = dict(fail_to_pass=f2p, hidden_tests=stored['hidden_tests'], pass_to_pass=sorted(p2p))
        config = {**config, 'generation': {**config['generation'], 'stability_runs': runs}}
        with tempfile.TemporaryDirectory() as out:
            await verify_patch(spec, record, row['answer'], workspace, config, lock, out)
        return
    if kind == 'test_ids':
        with tempfile.TemporaryDirectory(prefix='rlm-reverify-probe-') as scratch:
            checkout = workspace.checkout(Path(scratch) / 'probe')
            for patch in filter(None, (spec.setup_patch, spec.probe_patch)):
                ok, message = await apply_patch(checkout, patch)
                if not ok:
                    raise Rejected('patch_does_not_apply', message)
            async with lock:
                probe = [await run_tests(workspace, checkout, timeout_s=timeout) for _ in range(runs)]
        truth = sorted({base_id(i) for i in stable(probe, lambda o: o in FAIL) & p2p})
    elif kind == 'symbols' and spec.setup_patch:
        truth = symbols
    else:
        script = (Path(reference['_dir']) / 'oracle.py').read_text(encoding='utf-8')
        truth, _ = await run_oracle(script, spec, workspace, config)
    expected = normalize(truth, kind, spec.answer_format)
    if not matches(normalize(row['answer'], kind, spec.answer_format), expected):
        raise Rejected('answer_no_longer_matches', f'{str(expected)[:300]}')


async def verify_pool(config, root, manifest_path, *, runs=1, log=print):
    root, manifest = Path(root), Path(manifest_path)
    work = root / config['work_dir']
    specs = {r['name']: RepoSpec.from_config(r) for r in config['repositories']}
    lock = asyncio.Semaphore(config['generation']['test_concurrency'])
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    failures = []

    async def one(row):
        repo = specs[row['repo']['name']]
        workspace = Workspace(repo, root / config['sources_dir'], config['python'])
        reference_dir = manifest.parent / row['reference_path']
        reference = read_json(reference_dir / 'reference.json')
        reference['_dir'] = str(reference_dir)
        baseline = read_json(work / 'repos' / repo.slug / 'baseline.json')
        try:
            await verify_task(row, reference, workspace, baseline, config, lock, runs)
        except Rejected as exc:
            failures.append(dict(task_id=row['task_id'], code=exc.code, detail=exc.detail[:500]))
            log(f'[verify] {row["task_id"]}: {exc.code}')

    await asyncio.gather(*(one(row) for row in rows))
    return dict(verified_total=len(rows) - len(failures), failed=failures)
