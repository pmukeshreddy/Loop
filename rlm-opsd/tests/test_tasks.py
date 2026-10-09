import copy
import json
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
