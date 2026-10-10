"""Audit the generated pool; run with .venv/bin/python from the repo root."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from rlm_opsd.tasks.build import load_tasks


manifest = Path('data/manifest.jsonl')
rows = [json.loads(line) for line in manifest.read_text().splitlines()]
build = json.loads(Path('data/build-report.json').read_text())
assert build['manifest_sha256'] == hashlib.sha256(manifest.read_bytes()).hexdigest()
assert len(rows) == build['generated_total'] == build['verified_total'] == build['written_total'] == 360
splits = Counter(row['split'] for row in rows)
assert splits == {'train': 300, 'dev_behavior': 60}

distributions = defaultdict(lambda: defaultdict(Counter))
labels = defaultdict(set)
source_hashes = defaultdict(set)
variants = defaultdict(set)
for row in rows:
    family, knobs = row['family'], row['knobs']
    for key in ('needles', 'hops', 'files', 'records', 'label_count', 'temporal_filter', 'cutoff_date', 'pair_relation'):
        # Default needles/hops on unrelated generators are not sampled settings.
        if key in build['config']['family_knobs'][family]:
            distributions[family][key][str(knobs[key])] += 1
    labels[row['split']].update(knobs.get('labels', []) if family in ('linear_aggregation', 'quadratic_pairs') else [])
    params = knobs['query_params']
    kind = family + ':' + params.get('operation', params.get('relation', 'default'))
    variants[kind].add(knobs['query_variant'])
    source_hashes[row['split']].update(ref['sha256'] for ref in row['source_refs'] if ref['dataset'] == 'PolyAI/banking77')
    if family == 'small_context_control':
        assert row['context_chars'] < build['config']['direct_read_max_chars']

# Check the guard by advancing once: it rejects coverage before yielding a row.
try:
    next(load_tasks(manifest, split='train'))
except ValueError as exc:
    assert 'coverage' in str(exc)
    training_guard = str(exc)
else:
    raise AssertionError('Incomplete heldout coverage unexpectedly released training data')

history_snapshot = Path('/tmp/opsd-single-path-log-hashes.json')
history_count = None
if history_snapshot.exists():
    history = json.loads(history_snapshot.read_text())
    for name, expected in history.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
    history_count = len(history)

result = {
    'manifest_sha256': build['manifest_sha256'],
    'split_counts': dict(splits),
    'family_counts': dict(Counter(row['family'] for row in rows)),
    'sampled_knob_distributions': {family: dict(values) for family, values in distributions.items()},
    'selected_label_counts_by_split': {split: len(values) for split, values in labels.items()},
    'query_variants_by_type': {kind: sorted(values) for kind, values in variants.items()},
    'train_dev_shared_normalized_source_texts': len(source_hashes['train'] & source_hashes['dev_behavior']),
    'heldout_coverage_complete': build['decontamination']['coverage_complete'],
    'training_loader_guard': training_guard,
    'historical_log_files_unchanged': history_count,
    'gpu_results': 'not run',
}
print(json.dumps(result, indent=2, sort_keys=True))
