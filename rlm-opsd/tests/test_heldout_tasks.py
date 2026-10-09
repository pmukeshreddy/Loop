import pytest


def test_oolong_requires_trec_coarse_and_never_exposes_labelled_context():
    from rlm_opsd.tasks.heldout import adapt_heldout
    raw = dict(id=5, dataset='trec_coarse', context_window_text='Date: d || User: 1 || Instance: Where?',
               context_window_text_with_labels='SECRET LABEL', question='Count locations',
               answer='1', answer_type='numeric', context_window_id=9, context_len=1024)
    task = adapt_heldout('oolong', raw, revision='pinned', license='source-license')
    assert task.split == 'eval_heldout' and task.answer == 1
    assert 'SECRET LABEL' not in str(task.context)
    with pytest.raises(ValueError, match='trec_coarse'):
        adapt_heldout('oolong', {**raw, 'dataset':'agnews'}, revision='pinned', license='test')


def test_pairs_cannot_load_without_matching_unlabelled_context():
    from rlm_opsd.tasks.heldout import adapt_heldout
    raw = dict(id='1', question='Which pairs?', answer=['(1, 2)'], type='list_of_answers')
    with pytest.raises(ValueError, match='context'):
        adapt_heldout('oolong_pairs', raw, revision='pinned', license='MIT')
    task = adapt_heldout('oolong_pairs', raw, revision='pinned', license='MIT',
                        context_record=dict(dataset='trec_coarse', context_window_text='entry',
                                            context_len=1024, context_window_id=0), context_len=1024)
    assert task.answer == ['(1, 2)'] and task.split == 'eval_heldout'


def test_longbench_filters_codeqa_and_includes_choices():
    from rlm_opsd.tasks.heldout import adapt_heldout
    raw = dict(_id='x', domain='Code Repository Understanding', sub_domain='Code repo QA',
               context='def f(): pass', question='Which function?', choice_A='f', choice_B='g',
               choice_C='h', choice_D='i', answer='A')
    task = adapt_heldout('longbench_v2_codeqa', raw, revision='pinned', license='Apache-2.0')
    assert task.answer == 'A' and task.answer_type == 'multiple_choice'
    assert 'A. f' in task.query and task.context == raw['context']
    with pytest.raises(ValueError, match='Code'):
        adapt_heldout('longbench_v2_codeqa', {**raw, 'domain':'Other'}, revision='pinned', license='test')


def test_browsecomp_requires_exactly_one_thousand_distinct_documents():
    from rlm_opsd.tasks.heldout import adapt_heldout
    raw = dict(query_id='b', query='Question?', answer='Answer', gold_docs=[dict(docid='0', text='evidence', url='url')])
    docs = [dict(docid=str(i), text=f'document {i}') for i in range(1000)]
    with pytest.raises(ValueError, match='1000'):
        adapt_heldout('browsecomp_plus', raw, revision='pinned', license='MIT', documents=docs[:2])
    task = adapt_heldout('browsecomp_plus', raw, revision='pinned', license='MIT', documents=docs)
    assert len(task.context) == 1000 and len(task.source_refs) == 1000


def test_sniah_imports_reserved_fixture_without_relabelling_generated_train_data():
    from rlm_opsd.tasks.heldout import adapt_heldout
    raw = dict(index=2, input='Hay. A special number for key-a is 47.\nWhat is the special number for key-a?',
               outputs=['47'])
    task = adapt_heldout('sniah', raw, revision='fixture-reserved', license='test')
    assert task.answer == '47' and task.split == 'eval_heldout'
    assert task.query == 'What is the special number for key-a?'
    assert task.family == 'sniah'


def test_snapshot_loader_filters_only_the_required_subset_and_preserves_eval_split(tmp_path):
    import json
    from rlm_opsd.tasks.heldout import load_heldout_snapshot
    raw = dict(id=5, dataset='trec_coarse', context_window_text='Instance: Where is Paris?',
               question='Count locations', answer='1', answer_type='numeric', context_window_id=9)
    path = tmp_path / 'snapshot.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in [raw, {**raw, 'dataset':'agnews'}]) + '\n')
    tasks = list(load_heldout_snapshot(path, benchmark='oolong', revision='pinned', license='fixture'))
    assert len(tasks) == 1 and tasks[0].split == 'eval_heldout'
    assert tasks[0].source_refs[0]['dataset'] == 'TREC'
    # Duplicate source rows are rejected, not silently used twice.
    path.write_text(json.dumps([raw, raw]))
    with pytest.raises(ValueError, match='duplicate'):
        list(load_heldout_snapshot(path, benchmark='oolong', revision='pinned', license='fixture'))
