import copy
import json
import re
from pathlib import Path

import pytest


FAMILIES = ['sparse_retrieval', 'multi_hop', 'linear_aggregation',
            'quadratic_pairs', 'repo_qa', 'small_context_control']


def corpus():
    from rlm_opsd.tasks.sources import ClassificationCorpus
    return ClassificationCorpus.from_records([
        dict(id='a', text='My bank card has not arrived in the post.', label='card_arrival'),
        dict(id='b', text='When will my new debit card be delivered?', label='card_arrival'),
        dict(id='c', text='What rate applies when converting dollars to euros?', label='exchange_rate'),
        dict(id='d', text='How do you calculate foreign currency conversions?', label='exchange_rate'),
    ], name='test-fixture', revision='fixture-v1', license='CC0-1.0')


def spec(family, *, seed=17, structure='str', encoding='jsonl', split='train', **knobs):
    from rlm_opsd.tasks import TaskSpec
    return TaskSpec(family=family, seed=seed, split=split, knobs=dict(
        target_chars=2048, structure='list' if family == 'repo_qa' else structure,
        encoding='markdown' if family == 'repo_qa' else encoding,
        entries=12, needles=3, hops=3, users=4, query_type='count',
        labels=['card_arrival', 'exchange_rate'], **knobs))


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('structure', ['str', 'list'])
def test_generators_are_seeded_and_answers_recomputed(family, structure):
    from rlm_opsd.tasks import generate, verify_answer
    recipe = spec(family, structure=structure)
    task = generate(recipe, corpus())
    assert task == generate(recipe, corpus())
    assert task.context != generate(spec(family, structure=structure, seed=18), corpus()).context
    assert verify_answer(task, corpus()) == task.answer
    assert sum(map(len, task.context)) if isinstance(task.context, list) else len(task.context)
    assert task.source and task.source_refs and task.tags
    altered = copy.deepcopy(task)
    altered.answer = 'deliberately incorrect'
    assert verify_answer(altered, corpus()) == task.answer
    assert verify_answer(altered, corpus()) != altered.answer


@pytest.mark.parametrize('encoding', ['plain', 'jsonl', 'csv', 'logs', 'markdown'])
@pytest.mark.parametrize('structure', ['str', 'list'])
def test_record_formats_preserve_unicode_newlines_and_delimiters(encoding, structure):
    from rlm_opsd.tasks.codec import render_records, parse_records
    records = [dict(kind='entry', user=3, date='2023-04-01', text='café, "quoted"\nline | bar'),
               dict(kind='entry', user=5, date='2023-03-31', text='next')]
    context = render_records(records, encoding=encoding, structure=structure, chunk_chars=50)
    assert parse_records(context, encoding) == records


@pytest.mark.parametrize('family', ['sparse_retrieval', 'multi_hop', 'linear_aggregation', 'quadratic_pairs'])
@pytest.mark.parametrize('encoding', ['plain', 'csv', 'logs', 'markdown'])
def test_generators_work_in_each_record_encoding(family, encoding):
    from rlm_opsd.tasks import generate, verify_answer
    task = generate(spec(family, encoding=encoding), corpus())
    assert verify_answer(task, corpus()) == task.answer


def test_label_verifier_uses_context_dates_and_source_annotations():
    from rlm_opsd.tasks import generate, verify_answer
    from rlm_opsd.tasks.codec import render_records
    task = generate(spec('linear_aggregation'), corpus())
    task.knobs['query_params'] = dict(operation='count', label='card_arrival', after='2023-03-31')
    task.context = render_records([
        dict(kind='entry', user=1, date='2023-03-31', text='My bank card has not arrived in the post.'),
        dict(kind='entry', user=1, date='2023-04-01', text='When will my new debit card be delivered?'),
        dict(kind='entry', user=2, date='2023-04-02', text='What rate applies when converting dollars to euros?'),
    ], encoding='jsonl', structure='str')
    assert verify_answer(task, corpus()) == 1
    task.knobs['query_params']['operation'] = 'most_frequent'
    # Ties have a documented lexicographic tie-break.
    assert verify_answer(task, corpus()) == 'card_arrival'


def test_pair_verifier_handles_duplicate_users_and_cross_entry_conditions():
    from rlm_opsd.tasks import generate, verify_answer
    from rlm_opsd.tasks.codec import render_records
    task = generate(spec('quadratic_pairs'), corpus())
    task.knobs['query_params'] = dict(labels=['card_arrival'], relation='both_have_any', after=None)
    task.context = render_records([
        dict(kind='entry', user=1, date='2023-04-01', text='My bank card has not arrived in the post.'),
        dict(kind='entry', user=1, date='2023-04-02', text='When will my new debit card be delivered?'),
        dict(kind='entry', user=2, date='2023-04-01', text='My bank card has not arrived in the post.'),
        dict(kind='entry', user=3, date='2023-04-01', text='What rate applies when converting dollars to euros?'),
    ], encoding='jsonl', structure='str')
    assert verify_answer(task, corpus()) == ['(1, 2)']


def test_sparse_verifier_rejects_near_match_distractors():
    from rlm_opsd.tasks import generate, verify_answer
    from rlm_opsd.tasks.codec import render_records
    task = generate(spec('sparse_retrieval'), corpus())
    task.knobs['query_params'] = dict(keys=['parcel-10'])
    task.context = render_records([
        dict(kind='fact', key='parcel-100', value='wrong'),
        dict(kind='fact', key='parcel-10', value='right'),
    ], encoding='jsonl', structure='str')
    assert verify_answer(task, corpus()) == 'right'


def test_multihop_verifier_traverses_documents_and_detects_broken_chain():
    from rlm_opsd.tasks import generate, verify_answer
    from rlm_opsd.tasks.codec import render_records
    task = generate(spec('multi_hop'), corpus())
    task.knobs['query_params'] = dict(start='A', hops=2)
    task.context = render_records([
        dict(kind='link', key='A', target='B'), dict(kind='link', key='B', target='C'),
        dict(kind='terminal', key='C', value='Oslo'), dict(kind='terminal', key='B', value='wrong')
    ], encoding='jsonl', structure='list')
    assert verify_answer(task, corpus()) == 'Oslo'
    task.knobs['query_params']['hops'] = 3
    with pytest.raises(ValueError, match='chain'):
        verify_answer(task, corpus())


def test_repo_verifier_reads_ast_not_planted_answer():
    from rlm_opsd.tasks import generate, verify_answer
    task = generate(spec('repo_qa'), corpus())
    task.knobs['query_params'] = dict(operation='callers', symbol='target')
    task.context = ['# File: lib.py\n```python\ndef target():\n    return 3\n```',
                    '# File: app.py\n```python\nfrom lib import target\ndef use():\n    return target()\n```']
    assert verify_answer(task, corpus()) == ['app.py:use']
    task.knobs['query_params'] = dict(operation='definition', symbol='target')
    assert verify_answer(task, corpus()) == 'lib.py'


def test_classification_sources_reject_trec_unknown_labels_and_conflicting_labels():
    from rlm_opsd.tasks.sources import ClassificationCorpus
    for name in ['TREC', 'trec_coarse', 'CogComp/trec']:
        with pytest.raises(ValueError, match='TREC'):
            ClassificationCorpus.from_records([dict(id='1', text='x', label='a')],
                                               name=name, revision='v1', license='test')
    with pytest.raises(ValueError, match='conflicting'):
        ClassificationCorpus.from_records([dict(id='1', text='Same text!', label='a'),
                                            dict(id='2', text='same TEXT', label='b')],
                                          name='fixture', revision='v1', license='test')
    with pytest.raises(ValueError, match='unknown'):
        corpus().label_for('Not in the corpus')


def test_generation_rejects_eval_split_and_invalid_task_knobs():
    from rlm_opsd.tasks import generate, TaskSpec
    with pytest.raises(ValueError, match='heldout'):
        generate(spec('sparse_retrieval', split='eval_heldout'), corpus())
    for family, knobs in [('multi_hop', dict(hops=1)), ('sparse_retrieval', dict(needles=9)),
                          ('small_context_control', dict(target_chars=32768, direct_read_max_chars=16384))]:
        with pytest.raises(ValueError):
            generate(TaskSpec(family=family, seed=0, split='train', knobs=knobs), corpus())


def test_banking_import_drops_ambiguous_rows_only_when_explicit_and_reports_them(tmp_path):
    import hashlib
    from rlm_opsd.tasks.sources import ClassificationCorpus
    path = tmp_path / 'bank.csv'
    path.write_text('text,category\nSame text!,a\nsame TEXT,b\nUnique,c\n', encoding='utf-8')
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='conflicting'):
        ClassificationCorpus.from_banking_csv(path, sha256=checksum, revision='fixture', partition='train')
    clean = ClassificationCorpus.from_banking_csv(path, sha256=checksum, revision='fixture', partition='train',
                                                  ambiguity_policy='drop')
    assert [r['text'] for r in clean.records] == ['Unique']
    assert clean.import_report['ambiguous_rows_dropped'] == 2
    assert clean.import_report['raw_rows'] == 3
    with pytest.raises(ValueError, match='checksum'):
        ClassificationCorpus.from_banking_csv(path, sha256='0' * 64, revision='fixture', partition='train')


@pytest.mark.parametrize('family', ['linear_aggregation', 'quadratic_pairs'])
def test_seeded_label_subsets_use_the_full_corpus(family):
    from rlm_opsd.tasks import generate, verify_answer, TaskSpec
    from rlm_opsd.tasks.sources import ClassificationCorpus
    source = ClassificationCorpus.from_records([
        dict(id=str(i), text=f'Classification example number {i}', label=f'intent_{i}') for i in range(10)
    ], name='full-label-fixture', revision='v1', license='CC0-1.0')
    subsets = set()
    for seed in range(40):
        knobs = spec(family).knobs
        knobs.pop('labels')
        knobs['label_count'] = 3
        recipe = TaskSpec(family, knobs, seed, 'train')
        task = generate(recipe, source)
        assert task == generate(recipe, source)
        assert len(task.knobs['labels']) == 3
        assert verify_answer(task, source) == task.answer
        subsets.add(tuple(task.knobs['labels']))
    assert len(subsets) > 1
    assert set().union(*map(set, subsets)) == {f'intent_{i}' for i in range(10)}


@pytest.mark.parametrize('count', [0, 3, True])
def test_label_count_must_fit_the_corpus(count):
    from rlm_opsd.tasks import generate, TaskSpec
    knobs = spec('linear_aggregation').knobs
    knobs.pop('labels')
    knobs['label_count'] = count
    with pytest.raises(ValueError, match='label_count'):
        generate(TaskSpec('linear_aggregation', knobs, 17, 'train'), corpus())


def test_label_count_and_explicit_labels_cannot_conflict():
    from rlm_opsd.tasks import generate
    with pytest.raises(ValueError, match='label_count'):
        generate(spec('linear_aggregation', label_count=1), corpus())


@pytest.mark.parametrize('family', ['linear_aggregation', 'quadratic_pairs'])
@pytest.mark.parametrize('enabled', [True, False])
def test_varied_cutoff_applies_to_query_and_verified_answer(family, enabled):
    from rlm_opsd.tasks import generate, verify_answer
    tasks = [generate(spec(family, cutoff_date=cutoff, temporal_filter=enabled), corpus())
             for cutoff in ['2022-12-31', '2023-06-30']]
    assert tasks[0].context == tasks[1].context
    for task, cutoff in zip(tasks, ['2022-12-31', '2023-06-30']):
        assert task.knobs['query_params']['after'] == (cutoff if enabled else None)
        assert (cutoff in task.query) == enabled
        assert verify_answer(task, corpus()) == task.answer
    if enabled:
        assert tasks[0].answer
        assert tasks[1].answer in (0, [])
    else:
        assert tasks[0].answer == tasks[1].answer


@pytest.mark.parametrize('count', [4, 13, 24])
def test_small_context_record_count_changes_real_records(count):
    from rlm_opsd.tasks import generate, verify_answer
    from rlm_opsd.tasks.codec import parse_records
    task = generate(spec('small_context_control', records=count), corpus())
    records = parse_records(task.context, task.knobs['encoding'])
    quantities = [r for r in records if r['kind'] == 'quantity']
    assert len(quantities) == count
    assert sum(r['group'] == task.knobs['query_params']['group'] for r in quantities) == (count + 1) // 2
    assert verify_answer(task, corpus()) == task.answer


@pytest.mark.parametrize('family, overrides', [
    ('sparse_retrieval', {}), ('multi_hop', {}), ('small_context_control', {}),
    ('linear_aggregation', {'query_type': 'count'}),
    ('linear_aggregation', {'query_type': 'most_frequent'}),
    ('quadratic_pairs', {'pair_relation': 'both_have_any'}),
    ('quadratic_pairs', {'pair_relation': 'cover_labels'}),
    ('repo_qa', {'repo_query_type': 'definition'}),
    ('repo_qa', {'repo_query_type': 'callers'}),
    ('repo_qa', {'repo_query_type': 'config'}),
])
def test_each_query_type_has_seeded_wordings_with_verified_answers(family, overrides):
    from rlm_opsd.tasks import generate, verify_answer, TaskSpec
    wordings = set()
    for seed in range(40):
        knobs = spec(family).knobs
        knobs.update(overrides)
        recipe = TaskSpec(family, knobs, seed, 'train')
        task = generate(recipe, corpus())
        assert task == generate(recipe, corpus())
        assert verify_answer(task, corpus()) == task.answer
        # IDs, label order and the queried intent cannot masquerade as rephrasing.
        wording = re.sub(r'[0-9a-fA-F]{16}', '<ID>', task.query)
        wording = re.sub(r'card_arrival|exchange_rate', '<intent>', wording)
        wordings.add(wording)
    assert 3 <= len(wordings) <= 4
