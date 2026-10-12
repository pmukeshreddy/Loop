"""Build a candidate's starting state, executable ground truth and context."""
import re
import tempfile
from pathlib import Path

from .analysis import diff_symbols
from .models import size_bucket
from .repos import apply_patch, inventory, patch_files, render_context, run_tests, select_documents


class Rejected(Exception):
    def __init__(self, code, detail=''):
        self.code, self.detail = code, detail
        super().__init__(f'{code}: {detail}')


def base_id(nodeid):
    """Parametrized cases compare at the test-function level."""
    return re.sub(r'\[.*\]$', '', nodeid.strip())


def stable(runs, predicate):
    """Node IDs for which `predicate(outcome)` holds on every run."""
    ids = set(runs[0].outcomes)
    for run in runs[1:]:
        ids &= set(run.outcomes)
    return {i for i in ids if all(predicate(run.outcomes[i]) for run in runs)}


def flaky(runs):
    ids = set().union(*(set(r.outcomes) for r in runs))
    return sorted(i for i in ids if len({r.outcomes.get(i) for r in runs}) > 1)


FAIL = ('failed', 'error')
PASS = ('passed', 'xfailed')


def failure_log(run, limit=60000):
    """The real pytest output; long failure sections keep their head and summary."""
    text = run.log
    if len(text) <= limit:
        return text
    marker = text.rfind('short test summary info')
    summary = text[text.rfind('\n', 0, marker) + 1:] if marker >= 0 else text[-8000:]
    head = text[:max(0, limit - len(summary) - 200)]
    return head + f'\n... [{len(text) - len(head) - len(summary)} characters of repeated failure output omitted] ...\n' + summary


async def _runs(workspace, checkout, n, timeout_s, test_lock, selectors=None):
    runs = []
    for _ in range(n):
        async with test_lock:
            run = await run_tests(workspace, checkout, selectors=selectors, timeout_s=timeout_s)
        if run.timed_out:
            raise Rejected('test_timeout', f'pytest exceeded {timeout_s}s')
        runs.append(run)
    return runs


def _non_test(spec, patch, label):
    files = patch_files(patch)
    if not files:
        raise Rejected('malformed_patch', f'{label} names no files')
    tests = [f for f in files if spec.is_test_path(f)]
    if tests:
        raise Rejected('patch_touches_tests', f'{label} edits test files {tests}')
    return files


async def materialize(spec, workspace, baseline, config, test_lock, out_dir):
    """Return the materialized record; raise Rejected with a reason code."""
    repo, gen, filters, ctx = workspace.spec, config['generation'], config['filters'], config['context']
    runs_n, timeout = gen['stability_runs'], gen['test_timeout_s']
    base_pass = set(baseline['stable_passing'])
    record = dict(setup_files=[], fail_to_pass=[], pass_to_pass=[], impact_tests=[], hidden_tests=[],
                  ground_truth_symbols=[], flaky=[], logs=[])
    out_dir = Path(out_dir)
    with tempfile.TemporaryDirectory(prefix='rlm-mat-') as scratch:
        state = workspace.checkout(Path(scratch) / 'state')
        if spec.setup_patch:
            record['setup_files'] = _non_test(repo, spec.setup_patch, 'setup_patch')
            ok, message = await apply_patch(state, spec.setup_patch)
            if not ok:
                raise Rejected('setup_patch_does_not_apply', message)
            runs = await _runs(workspace, state, runs_n, timeout, test_lock)
            if any(k.startswith('collect::') for k in runs[0].failing()):
                raise Rejected('setup_breaks_collection', ', '.join(sorted(runs[0].failing())[:5]))
            failing = stable(runs, lambda o: o in FAIL)
            f2p = sorted(failing & base_pass)
            record['flaky'] = flaky(runs)
            if not f2p:
                raise Rejected('setup_breaks_no_tests', 'no baseline-passing test fails on every run')
            fraction = len(f2p) / max(1, len(base_pass))
            if fraction > filters['max_setup_fail_fraction']:
                raise Rejected('setup_too_destructive', f'{len(f2p)} of {len(base_pass)} tests fail')
            p2p = stable(runs, lambda o: o in PASS) & base_pass
            record.update(fail_to_pass=f2p, pass_to_pass=sorted(p2p), setup_fail_fraction=round(fraction, 4))
            (out_dir / 'setup-test.log').write_text(runs[0].log, encoding='utf-8')
            record['ground_truth_symbols'] = diff_symbols(
                (path, (workspace.tree / path).read_text(encoding='utf-8') if (workspace.tree / path).exists() else None,
                 (state / path).read_text(encoding='utf-8')) for path in record['setup_files'])
            if spec.include_failure_log:
                record['logs'].append(('pytest run on the current branch', failure_log(runs[0])))
        else:
            p2p = base_pass
            record['pass_to_pass'] = sorted(p2p)
        if spec.probe_patch:
            _non_test(repo, spec.probe_patch, 'probe_patch')
            probe = workspace.checkout(Path(scratch) / 'probe')
            if spec.setup_patch:
                await apply_patch(probe, spec.setup_patch)
            ok, message = await apply_patch(probe, spec.probe_patch)
            if not ok:
                raise Rejected('probe_patch_does_not_apply', message)
            runs = await _runs(workspace, probe, runs_n, timeout, test_lock)
            if any(k.startswith('collect::') for k in runs[0].failing()):
                raise Rejected('probe_breaks_collection', ', '.join(sorted(runs[0].failing())[:5]))
            impact = sorted({base_id(i) for i in stable(runs, lambda o: o in FAIL) & p2p})
            mixed = {base_id(i) for i in flaky(runs)} & set(impact)
            if mixed:
                raise Rejected('flaky_impact', f'{sorted(mixed)[:5]}')
            if not filters['min_impact_tests'] <= len(impact) <= filters['max_impact_tests']:
                raise Rejected('impact_size_out_of_range', f'{len(impact)} tests newly fail')
            # Answers must be derivable from the context: each node ID names the file that defines the test.
            for nodeid in impact:
                path, _, name = nodeid.partition('::')
                function = name.split('::')[-1]
                text = (probe / path).read_text(encoding='utf-8') if (probe / path).is_file() else ''
                if not re.search(rf'\bdef {re.escape(function)}\s*\(', text):
                    raise Rejected('impact_ids_not_file_faithful', f'{nodeid} is not defined in {path}')
            record['impact_tests'] = impact
            (out_dir / 'probe-test.log').write_text(runs[0].log, encoding='utf-8')
        if spec.hidden_tests_patch:
            files = patch_files(spec.hidden_tests_patch)
            if not files or not all(repo.is_test_path(f) for f in files):
                raise Rejected('hidden_tests_outside_test_paths', f'{files}')
            hidden = workspace.checkout(Path(scratch) / 'hidden')
            if spec.setup_patch:
                await apply_patch(hidden, spec.setup_patch)
            ok, message = await apply_patch(hidden, spec.hidden_tests_patch)
            if not ok:
                raise Rejected('hidden_tests_do_not_apply', message)
            runs = await _runs(workspace, hidden, runs_n, timeout, test_lock, selectors=files)
            collected = set(runs[0].outcomes)
            if not collected or any(k.startswith('collect::') for k in collected):
                raise Rejected('hidden_tests_not_collected', ', '.join(sorted(collected)[:5]))
            failing = stable(runs, lambda o: o in FAIL)
            if not failing:
                raise Rejected('hidden_tests_pass_before_fix', 'acceptance tests already pass')
            record['hidden_tests'] = sorted(failing)
            record['hidden_test_files'] = files
        if spec.answer_kind == 'patch' and not (record['fail_to_pass'] or record['hidden_tests']):
            raise Rejected('patch_task_without_failing_tests')
        documents = inventory(repo, state, exclude=ctx['exclude'], max_file_chars=ctx['max_file_chars'])
        try:
            chosen = select_documents(documents, scope=spec.context.scope, files=spec.context.files,
                                      max_chars=ctx['max_chars'], max_documents=ctx['max_documents'])
        except ValueError as exc:
            raise Rejected('context_files_missing', str(exc)) from exc
        for evidence in spec.evidence:
            if evidence.path not in {d.path for d in documents}:
                raise Rejected('evidence_path_missing', evidence.path)
        context = render_context(chosen, record['logs'])
        chars = sum(map(len, context))
        if spec.primary_behavior == 'direct_solve' and chars >= ctx['direct_read_max_chars']:
            raise Rejected('direct_solve_context_too_large', f'{chars} chars')
        try:
            bucket = size_bucket(chars, ctx['size_buckets'])
        except ValueError as exc:
            raise Rejected('context_too_large', str(exc)) from exc
        record.update(context_chars=chars, size_bucket=bucket, documents=[d.path for d in chosen],
                      logs=[title for title, _ in record['logs']])
        return record, context


async def state_checkout(workspace, spec, dest):
    """The solver's starting state (setup patch applied) in `dest`."""
    checkout = workspace.checkout(dest)
    if spec.setup_patch:
        ok, message = await apply_patch(checkout, spec.setup_patch)
        if not ok:
            raise Rejected('setup_patch_does_not_apply', message)
    return checkout
