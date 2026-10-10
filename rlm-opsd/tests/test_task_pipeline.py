import copy
import json
from pathlib import Path

import pytest

from test_tasks import corpus, spec


def test_decontamination_reports_exact_near_source_and_content_overlap():
    from rlm_opsd.tasks import generate
    from rlm_opsd.tasks.decontam import decontaminate, HeldoutIndex, HeldoutRecord
    base = generate(spec('sparse_retrieval'), corpus())
    candidates = []
    for key, query in [('exact', '  WHERE is THE depot!?'),
                       ('near', 'which depot stores the blue parcel today'),
                       ('source', 'different question source'), ('content', 'different content question'),
                       ('clean', 'unrelated weather forecast')]:
        task = copy.deepcopy(base); task.task_id = key; task.query = query
        task.source_refs = [dict(dataset='candidate', revision='v1', item_id=key, sha256=key)]
        candidates.append(task)
    refs = [dict(dataset='candidate', revision='v2', item_id='source', sha256='other'),
            dict(dataset='alias', revision='v1', item_id='other', sha256='content')]
    index = HeldoutIndex(records=[HeldoutRecord(benchmark='sniah', task_id='h1', query='Where is the depot', source_refs=refs),
                                  HeldoutRecord(benchmark='sniah', task_id='h2', query='which depot stores the blue parcel now', source_refs=[])])
    kept, report = decontaminate(candidates, index, ngram_size=2, overlap_threshold=0.6)
    assert [task.task_id for task in kept] == ['clean']
    assert report['dropped_total'] == 4
    assert report['by_rule'] == dict(exact_query=1, near_query=1, shared_source=1, shared_content=1)
    assert report['input_total'] == report['kept_total'] + report['dropped_total']
    assert not report['coverage_complete']
    with pytest.raises(ValueError):
        decontaminate(candidates, index, ngram_size=0, overlap_threshold=1.1)


def test_exact_short_queries_and_empty_indexes_are_not_certified():
    from rlm_opsd.tasks import generate
    from rlm_opsd.tasks.decontam import decontaminate, HeldoutIndex, HeldoutRecord
    task = generate(spec('small_context_control'), corpus()); task.query = 'CITY?'
    index = HeldoutIndex(records=[HeldoutRecord(benchmark='sniah', task_id='h', query='city', source_refs=[])])
    kept, report = decontaminate([task], index, ngram_size=5, overlap_threshold=0.8)
    assert not kept and report['by_rule']['exact_query'] == 1
    kept, report = decontaminate([task], HeldoutIndex(), ngram_size=5, overlap_threshold=0.8)
    assert len(kept) == 1 and not report['coverage_complete']
    assert len(report['missing_benchmarks']) == 5


def config():
    return dict(seed=417, workers=2, size_buckets=[2048, 4096], structures=['str', 'list'],
                encodings=['plain', 'jsonl', 'csv', 'logs', 'markdown'],
                families={f: 1 for f in ['sparse_retrieval', 'multi_hop', 'linear_aggregation',
                                        'quadratic_pairs', 'repo_qa', 'small_context_control']},
                splits=dict(train=1, dev_behavior=1), direct_read_max_chars=3000,
                decontamination=dict(ngram_size=3, overlap_threshold=0.8),
                family_knobs={
                    'sparse_retrieval': {'needles': {'min': 1, 'max': 8}},
                    'multi_hop': {'hops': {'min': 2, 'max': 4}},
                    'linear_aggregation': {'label_count': {'min': 1, 'max': 2},
                                           'temporal_filter': {'choices': [True, False]},
                                           'cutoff_date': {'min': '2023-01-01', 'max': '2023-06-28'}},
                    'quadratic_pairs': {'label_count': 2, 'pair_relation': {'choices': ['both_have_any', 'cover_labels']}},
                    'repo_qa': {'files': {'min': 8, 'max': 64}},
                    'small_context_control': {'records': {'min': 4, 'max': 24}},
                })


def test_knob_ranges_are_seeded_inclusive_and_do_not_mutate_configuration():
    from rlm_opsd.tasks.build import plan_specs
    settings = config()
    settings.update(size_buckets=[2048], structures=['list'], splits=dict(train=512, dev_behavior=1))
    original = copy.deepcopy(settings)
    tasks, excluded = plan_specs(settings)
    assert settings == original
    assert (tasks, excluded) == plan_specs(copy.deepcopy(settings))
    for family, key, low, high in [('sparse_retrieval', 'needles', 1, 8), ('multi_hop', 'hops', 2, 4),
                                   ('repo_qa', 'files', 8, 64), ('small_context_control', 'records', 4, 24)]:
        values = [s.knobs[key] for s in tasks if s.family == family]
        assert all(type(value) is int and low <= value <= high for value in values)
        assert set(values) == set(range(low, high + 1))
    dense = [s.knobs for s in tasks if s.family == 'linear_aggregation']
    assert {k['temporal_filter'] for k in dense} == {True, False}
    assert all('2023-01-01' <= k['cutoff_date'] <= '2023-06-28' for k in dense)
    assert len({k['cutoff_date'] for k in dense}) > 10
    assert {s.knobs['pair_relation'] for s in tasks if s.family == 'quadratic_pairs'} == {'both_have_any', 'cover_labels'}
    for knobs in settings['family_knobs'].values():
        items = list(knobs.items())[::-1]
        knobs.clear()
        knobs.update(items)
    assert plan_specs(settings) == (tasks, excluded)
    settings['seed'] += 1
    assert [s.knobs for s in plan_specs(settings)[0]] != [s.knobs for s in tasks]


@pytest.mark.parametrize('value', [
    {'min': 8, 'max': 1}, {'min': 1}, {'choices': []}, {'choices': 'count'},
    {'min': True, 'max': 8}, {'min': 1.5, 'max': 8},
    {'min': '2023-02-30', 'max': '2023-06-01'},
    {'min': '2023-06-01', 'max': '2023-01-01'},
    {'min': 1, 'max': 8, 'choices': [1, 8]},
])
def test_invalid_knob_ranges_fail_before_generating(value):
    from rlm_opsd.tasks.build import plan_specs
    settings = config()
    settings['family_knobs']['sparse_retrieval']['needles'] = value
    with pytest.raises(ValueError, match='knob'):
        plan_specs(settings)


def test_parallel_pool_is_reproducible_materialized_and_incomplete_pool_blocked(tmp_path):
    from rlm_opsd.tasks.build import build_pool, load_tasks, verify_pool
    from rlm_opsd.tasks.decontam import HeldoutIndex
    first = tmp_path / 'first'; second = tmp_path / 'second'
    settings = config()
    report = build_pool(settings, first, corpora={'train': corpus(), 'dev_behavior': corpus()}, heldout=HeldoutIndex())
    settings['workers'] = 1
    build_pool(settings, second, corpora={'train': corpus(), 'dev_behavior': corpus()}, heldout=HeldoutIndex())
    assert (first / 'manifest.jsonl').read_bytes() == (second / 'manifest.jsonl').read_bytes()
    assert report['generated_total'] == 40  # 4 families*2 sizes*2 structures*2 splits + repo(4) + controls(4)
    assert report['decontamination']['coverage_complete'] is False
    assert report['grid_exclusions']
    rows = [json.loads(line) for line in (first / 'manifest.jsonl').read_text().splitlines()]
    assert len(rows) == 40 and len({r['task_id'] for r in rows}) == 40
    for row in rows:
        payload = json.loads((first / row['context_path']).read_text())
        length = len(payload) if isinstance(payload, str) else sum(map(len, payload))
        assert length == row['context_chars'] and length >= row['knobs']['target_chars']
        assert row['source_refs'] and row['source']
    with pytest.raises(ValueError, match='coverage'):
        list(load_tasks(first / 'manifest.jsonl', split='train'))
    assert verify_pool(first / 'manifest.jsonl', corpora={'train': corpus(), 'dev_behavior': corpus()}) == 40
    # Context-file corruption is detected before a row can reach the harness.
    context_path = first / rows[0]['context_path']
    context_path.write_text('"changed"')
    with pytest.raises(ValueError, match='context'):
        verify_pool(first / 'manifest.jsonl', corpora={'train': corpus(), 'dev_behavior': corpus()})


def test_manifest_reader_keeps_answers_out_of_opsd_input_and_eval_out_of_train(tmp_path):
    from rlm_opsd.tasks.build import build_pool, load_tasks
    from rlm_opsd.tasks.decontam import HeldoutIndex
    build_pool(config(), tmp_path, corpora={'train': corpus(), 'dev_behavior': corpus()}, heldout=HeldoutIndex())
    # An explicit inspection path is allowed, but may not masquerade as training release.
    rows = list(load_tasks(tmp_path / 'manifest.jsonl', split='dev_behavior', inspection_only=True))
    assert rows and all('answer' not in row and 'answer' not in row['info'] for row in rows)
    assert all('context' in row['info'] and row['prompt'][0]['content'] == row['info']['query'] for row in rows)
    with pytest.raises(ValueError, match='split'):
        list(load_tasks(tmp_path / 'manifest.jsonl', split='all'))


def test_complete_reserved_index_releases_pool_but_tampered_manifest_does_not(tmp_path):
    from rlm_opsd.tasks.build import build_pool, load_tasks
    from rlm_opsd.tasks.decontam import HeldoutIndex, HeldoutRecord
    from rlm_opsd.tasks.models import BENCHMARKS
    refs = [dict(dataset='reserved-fixture', revision='v1', item_id='document', sha256='unused-hash')]
    index = HeldoutIndex(records=[HeldoutRecord(name, name, 'A unique heldout fixture query', refs) for name in BENCHMARKS],
                        coverage={name: dict(complete=True, revision='fixture', record_count=1) for name in BENCHMARKS})
    build_pool(config(), tmp_path, corpora={'train': corpus(), 'dev_behavior': corpus()}, heldout=index)
    manifest = tmp_path / 'manifest.jsonl'
    released = list(load_tasks(manifest, split='train'))
    assert len(released) == 20 and all('answer' not in row for row in released)
    manifest.write_text(manifest.read_text() + '\n')
    with pytest.raises(ValueError, match='manifest changed'):
        list(load_tasks(manifest, split='train'))


def test_output_collision_and_context_path_traversal_are_rejected(tmp_path):
    from rlm_opsd.tasks.build import build_pool, load_tasks
    from rlm_opsd.tasks.decontam import HeldoutIndex
    build_pool(config(), tmp_path, corpora={'train': corpus(), 'dev_behavior': corpus()}, heldout=HeldoutIndex())
    with pytest.raises(ValueError, match='empty'):
        build_pool(config(), tmp_path, corpora={}, heldout=HeldoutIndex())
    path = tmp_path / 'manifest.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]['context_path'] = '../outside.json'
    path.write_text('\n'.join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match='escapes'):
        list(load_tasks(path, split='train', inspection_only=True))
