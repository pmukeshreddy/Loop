"""Independent verification of reference answers against executable evidence."""
import json
import math
from pathlib import Path
import re
import tempfile

from .analysis import normalize_symbol
from .materialize import FAIL, PASS, Rejected, base_id, state_checkout
from .repos import apply_patch, patch_files, run_python, run_tests


def _strip_fence(text):
    match = re.fullmatch(r'\s*```[a-zA-Z]*\s*\n(.*?)\n```\s*', text, re.S)
    return match[1] if match else text.strip()


def parse_answer(text, answer_format):
    """Decode a FINAL value for comparison; raises ValueError when malformed."""
    if answer_format == 'unified_diff':
        return _strip_fence(text) if text.lstrip().startswith('```') else text
    raw = _strip_fence(text)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        if answer_format == 'scalar':
            return raw.strip().strip('"\'')
        raise ValueError('answer is not valid JSON') from None
    if answer_format in ('set', 'ordered_list') and not isinstance(value, list):
        raise ValueError('answer must be a JSON list')
    if answer_format == 'object' and not isinstance(value, dict):
        raise ValueError('answer must be a JSON object')
    return value


def _scalar(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text) if re.fullmatch(r'-?\d+(\.\d+)?([eE]-?\d+)?', text) else text
        except ValueError:
            return text
    return json.dumps(value, sort_keys=True)


def _canon(value):
    """Recursively canonical JSON-like value: integral floats become ints, strings are stripped."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {str(k).strip(): _canon(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    return value


def normalize(value, answer_kind, answer_format):
    if answer_kind == 'test_ids':
        return sorted({base_id(str(v).strip().removeprefix('./')) for v in value})
    if answer_kind == 'symbols':
        items = [normalize_symbol(v) for v in value]
        return sorted(set(items)) if answer_format == 'set' else items
    if answer_format == 'set':
        return sorted({json.dumps(_canon(_scalar(v)), sort_keys=True) for v in value})
    if answer_format == 'ordered_list':
        return [_scalar(v) for v in value]
    if answer_format == 'object':
        return json.dumps(_canon(value), sort_keys=True)
    return _scalar(value)


def matches(left, right):
    if isinstance(left, float) and isinstance(right, float):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(matches(a, b) for a, b in zip(left, right))
    return left == right


def set_scores(predicted, truth):
    predicted, truth = set(predicted), set(truth)
    if not predicted and not truth:
        return 1.0, 1.0
    precision = len(predicted & truth) / len(predicted) if predicted else 0.0
    recall = len(predicted & truth) / len(truth) if truth else 0.0
    return round(precision, 4), round(recall, 4)


async def verify_patch(spec, record, patch, workspace, config, test_lock, out_dir):
    files = patch_files(patch)
    if not files:
        raise Rejected('reference_patch_malformed', 'no files in diff headers')
    touched_tests = [f for f in files if workspace.spec.is_test_path(f)]
    if touched_tests:
        raise Rejected('reference_patch_edits_tests', f'{touched_tests}')
    runs_n, timeout = config['generation']['stability_runs'], config['generation']['test_timeout_s']
    evidence = dict(patch_files=files)
    with tempfile.TemporaryDirectory(prefix='rlm-verify-') as scratch:
        checkout = await state_checkout(workspace, spec, Path(scratch) / 'state')
        ok, message = await apply_patch(checkout, patch)
        if not ok:
            raise Rejected('reference_patch_does_not_apply', message)
        if spec.hidden_tests_patch:
            ok, message = await apply_patch(checkout, spec.hidden_tests_patch)
            if not ok:
                raise Rejected('hidden_tests_do_not_apply_after_fix', message)
        targets = sorted(set(record['fail_to_pass']) | set(record['hidden_tests']))
        for attempt in range(runs_n):
            async with test_lock:
                run = await run_tests(workspace, checkout, selectors=targets, timeout_s=timeout)
            still_failing = sorted(t for t in targets if run.outcomes.get(t) not in PASS)
            if still_failing:
                (Path(out_dir) / 'verify-f2p.log').write_text(run.log, encoding='utf-8')
                raise Rejected('fail_to_pass_still_failing', f'run {attempt + 1}: {still_failing[:6]}')
        async with test_lock:
            full = await run_tests(workspace, checkout, timeout_s=timeout)
        (Path(out_dir) / 'verify-full.log').write_text(full.log, encoding='utf-8')
        regressions = sorted(t for t in record['pass_to_pass'] if full.outcomes.get(t) in FAIL)
        if regressions:
            raise Rejected('pass_to_pass_regression', f'{len(regressions)}: {regressions[:6]}')
        evidence.update(fail_to_pass_passing=len(targets), full_suite=dict(
            passed=len(full.passing()), failed=len(full.failing())), stability_runs=runs_n)
    return evidence


async def run_oracle(script, spec, workspace, config):
    outputs = []
    with tempfile.TemporaryDirectory(prefix='rlm-oracle-state-') as scratch:
        checkout = await state_checkout(workspace, spec, Path(scratch) / 'state')
        for _ in range(2):
            code, output, timed_out = await run_python(workspace, checkout, script,
                                                       timeout_s=config['generation']['oracle_timeout_s'])
            if timed_out:
                raise Rejected('oracle_timeout')
            lines = [line for line in output.strip().splitlines() if line.strip().startswith('{')]
            if code != 0 or not lines:
                raise Rejected('oracle_failed', output[-1200:])
            try:
                result = json.loads(lines[-1])
            except json.JSONDecodeError as exc:
                raise Rejected('oracle_output_not_json', lines[-1][:300]) from exc
            if 'unverifiable' in result:
                raise Rejected('oracle_unverifiable', str(result['unverifiable'])[:500])
            if 'answer' not in result:
                raise Rejected('oracle_output_missing_answer', lines[-1][:300])
            outputs.append(result['answer'])
    if json.dumps(outputs[0], sort_keys=True) != json.dumps(outputs[1], sort_keys=True):
        raise Rejected('oracle_nondeterministic')
    return outputs[0], output[-4000:]
