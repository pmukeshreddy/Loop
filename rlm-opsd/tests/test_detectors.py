"""Hand-labelled M4 trajectories; no model outputs or detector-derived expectations."""
import copy

import pytest


THRESHOLDS = dict(probe_max_chars=10, dump_threshold=25, read_threshold=15, many_hits=3,
                  subcall_max_chars=40, min_batch_chars=10, max_subcalls_expected={'fixture': 5},
                  hand_copy_min_chars=8, dense_coverage_min=0.8)


def turn(code='', *, stdout='', error=None, calls=(), finish=''):
    return dict(assistant_text=('```repl\n' + code + '\n```\n' if code else '') + finish,
                assistant_token_ids=[], code_blocks=[code] if code else [], stdout_truncated=stdout,
                stdout_raw_chars=len(stdout), error=error,
                subcalls=[dict(prompt_chars=n, output_chars=1, latency_s=0.1) for n in calls])


def trace(*turns, tags=(), final_type='FINAL', final_value='done', final_error=None, length=100):
    return dict(task_id='fixture', family='fixture', domain='test', tags=list(tags),
                prompt_variant='student', manual_version='manual_v1', turns=list(turns),
                final=dict(type=final_type, value=final_value, error=final_error),
                budget_hits={}, timings={}, context_metadata=dict(context_type='str',
                context_total_length=length, context_lengths=[]), size_bucket=128)


P = 'print(type(context), len(context))'
CASES = [
 ('D1', 'probe', True, trace(turn(P))),
 ('D1', 'raw-first', False, trace(turn('print(context)'))),
 ('D2', 'small-output', True, trace(turn('print(context[:10])'))),
 ('D2', 'raw-output', False, trace(turn('print(context)'))),
 ('D3', 'search-first', True, trace(turn(P), turn('pos = context.find("needle")'),
      turn('print(context[pos:pos + 30])'), tags=['sparse'])),
 ('D3', 'read-first', False, trace(turn('print(context[:30])'), turn('pos = context.find("needle")'), tags=['sparse'])),
 ('D4', 'changed-pattern', True, trace(turn('import re\nhits = re.findall("x", context)\nprint(len(hits))', stdout='0\n'),
      turn('hits = re.findall("y", context)'))),
 ('D4', 'same-pattern', False, trace(turn('import re\nhits = re.findall("x", context)\nprint(len(hits))', stdout='0\n'),
      turn('hits = re.findall("x", context)'))),
 ('D5', 'search-window', True, trace(turn(P), turn('pos = context.find("needle")'),
      turn('window = context[max(0, pos - 10):pos + 10]\nprint(window)'))),
 ('D5', 'unrelated-window', False, trace(turn(P), turn('pos = context.find("needle")'), turn('print(context[40:80])'))),
 ('D6', 'derived-pattern', True, trace(turn('pos = context.find("needle")\nname = context[pos:pos + 5]'),
      turn('next_pos = context.find(name)'))),
 ('D6', 'independent-pattern', False, trace(turn('pos = context.find("needle")'), turn('next_pos = context.find("other")'))),
 ('D7', 'checked-used-hit', True, trace(turn('pos = context.find("needle")'),
      turn('hit = context[max(0, pos - 5):pos + 5]\nanswer = llm_query(hit)', calls=[10], finish='FINAL_VAR(answer)'),
      final_type='FINAL_VAR', final_value='answer-value')),
 ('D7', 'unchecked-used-hit', False, trace(turn('pos = context.find("needle")', finish='FINAL_VAR(pos)'),
      final_type='FINAL_VAR', final_value='5')),
 ('D8', 'chunk-call', True, trace(turn('chunk = context[:20]\nout = llm_query(chunk)', calls=[20]))),
 ('D8', 'oversized-whole', False, trace(turn('out = llm_query(context)', calls=[100]))),
 ('D9', 'loop-calls', True, trace(turn('results = []\nfor start in range(0, 100, 20):\n    results.append(llm_query(context[start:start + 20]))', calls=[20]*5))),
 ('D9', 'single-call', False, trace(turn('out = llm_query(context[:20])', calls=[20]))),
 ('D10', 'batched-size', True, trace(turn('out = llm_query(context[:20])', calls=[20, 20]))),
 ('D10', 'too-many-tiny', False, trace(turn('out = llm_query(context[:5])', calls=[5]*6))),
 ('D11', 'stored-result', True, trace(turn('out = llm_query(context[:20])', calls=[20]))),
 ('D11', 'discarded-result', False, trace(turn('llm_query(context[:20])', calls=[20]))),
 ('D12', 'reuse', True, trace(turn('n = len(context)'), turn('print(n)'))),
 ('D12', 'replaced-before-read', False, trace(turn('n = len(context)'), turn('n = 3\nprint(n)'))),
 ('D13', 'different-literal', True, trace(turn('print(context[:20])', stdout='LONG_SECRET_123456789'), turn('x = "DIFFERENT_VALUE"'))),
 ('D13', 'copied-literal', False, trace(turn('print(context[:20])', stdout='LONG_SECRET_123456789'), turn('x = "LONG_SECRET_123456789"'))),
 ('D14', 'computed-answer', True, trace(turn('answer = sum([1, 2, 3])', finish='FINAL_VAR(answer)'), final_type='FINAL_VAR', final_value='6')),
 ('D14', 'literal-answer', False, trace(turn('answer = "guess"', finish='FINAL_VAR(answer)'), final_type='FINAL_VAR', final_value='guess')),
 ('D15', 'one-finish', True, trace(turn(finish='FINAL(7)'), final_value='7')),
 ('D15', 'missing-variable', False, trace(turn(finish='FINAL_VAR(missing)'), final_type='none', final_value='', final_error='missing variable')),
 ('D16', 'valid-code', 0.0, trace(turn('print(1)'))),
 ('D16', 'one-of-two-invalid', 0.5, trace(turn('for:', stdout='SyntaxError: invalid syntax', error='SyntaxError'), turn('print(1)'))),
 ('D17', 'fixed-error', True, trace(turn('print(1 / 0)', stdout='Traceback\nZeroDivisionError: division by zero', error='ZeroDivisionError'), turn('print(2)'))),
 ('D17', 'repeated-error', False, trace(turn('print(1 / 0)', stdout='Traceback\nZeroDivisionError: division by zero', error='ZeroDivisionError'),
      turn('print(1 / 0)', stdout='Traceback\nZeroDivisionError: division by zero', error='ZeroDivisionError'))),
 ('D18', 'overlap-union', 0.6, trace(turn('part = context[:40]\nprint(part)'), turn('print(context[20:60])'))),
 ('D18', 'partial', 0.1, trace(turn('print(context[:10])'))),
 ('D19', 'search-strategy', 'regex_filter', trace(turn(P), turn('import re\nhits = re.findall("x", context)'))),
 ('D19', 'direct-strategy', 'direct_read', trace(turn('print(context)'))),
]


def analyze(value, **changes):
    from rlm_opsd.detectors import DetectorConfig, analyze_trajectory

    return analyze_trajectory(value, DetectorConfig(**{**THRESHOLDS, **changes}))


@pytest.mark.parametrize('detector,label,expected,trajectory', CASES, ids=[f'{d}-{label}' for d,label,_,_ in CASES])
def test_hand_labelled_detector(detector, label, expected, trajectory):
    result = analyze(trajectory)
    assert result['detectors'][detector] == expected, result


def test_facts_track_aliases_order_provenance_and_reassignment_without_execution(tmp_path):
    target = tmp_path / 'must-not-exist'
    value = trace(turn(P), turn(f'open({str(target)!r}, "w").write("bad")\n'
        'blob = context\nprint(blob)\npos = blob.find("x")\nwindow = blob[pos:pos + 20]'))
    result = analyze(value)
    assert not target.exists()
    assert result['detectors']['D2'] is False
    assert result['detectors']['D3'] is None  # not a sparse task
    assert any(block['searches'] for block in result['facts'])
    assert any('blob' in block['assigned'] for block in result['facts'])
    cleared = analyze(trace(turn('blob = context\nblob = "short"\nprint(blob)')))
    assert cleared['detectors']['D2'] is True


def test_dead_code_and_unexecuted_helpers_do_not_create_fake_behavior():
    value = trace(turn('if False:\n    print(context)\ndef unused():\n    llm_query(context)\nprint(len(context))'))
    result = analyze(value)
    assert result['detectors']['D1'] is True
    assert result['detectors']['D2'] is True
    assert result['detectors']['D9'] is None  # no calls, not a fake pass
    assert result['counts']['subcall_count'] == 0


def test_coverage_uses_list_geometry_negative_slices_and_union():
    value = trace(turn('print(context[1][-10:])'), length=50)
    value['context_metadata'] = dict(context_type='list', context_total_length=50, context_lengths=[20,30])
    assert analyze(value)['detectors']['D18'] == 0.2
    unresolved = trace(turn('print(context[start:end])'))
    result = analyze(unresolved)
    assert result['detectors']['D18'] is None
    assert result['coverage_lower_bound'] == 0.0
    assert result['unknown_reasons']


def test_unknown_metadata_can_be_supplied_for_legacy_logs():
    from rlm_opsd.detectors import DetectorConfig, analyze_trajectory

    value = trace(turn('print(context[:10])'))
    metadata = value.pop('context_metadata')
    assert analyze(value)['detectors']['D18'] is None
    result = analyze_trajectory(value, DetectorConfig(**THRESHOLDS), task_metadata=metadata)
    assert result['detectors']['D18'] == 0.1


def test_tag_requirements_use_coverage_and_actual_calls_but_allow_small_direct_reads():
    dense = trace(turn(P), turn('results = []\nfor start in range(0, len(context), 20):\n'
        '    chunk = context[start:start + 20]\n    results.append(llm_query(chunk))', calls=[20]*5),
        turn('answer = len(results)', finish='FINAL_VAR(answer)'),
        tags=['large_context', 'dense', 'aggregate_in_code', 'output_in_variable'], final_type='FINAL_VAR', final_value='5')
    result = analyze(dense)
    assert result['task_tag_match'] is True, result
    assert result['detectors']['D18'] == 1.0
    assert result['counts']['subcall_count'] == 5
    assert result['counts']['subcall_mean_prompt_chars'] == 20
    assert result['detectors']['D19'] == 'chunk_subcall'
    small = trace(turn('print(context)', finish='FINAL(done)'), tags=['small_context'], length=5)
    assert analyze(small)['task_tag_match'] is True
    missing = copy.deepcopy(dense); missing.pop('context_metadata')
    assert analyze(missing)['task_tag_match'] is not True
    oversized = trace(turn('x = llm_query(context)', calls=[100], finish='FINAL(done)'), tags=['small_context'])
    assert analyze(oversized)['task_tag_match'] is False


@pytest.mark.parametrize('ending', ['FINAL(7) FINAL(8)', 'FINAL(7) FINAL_VAR(x)', 'FINAL(I will search for the answer)', 'FINAL()'])
def test_clean_finish_rejects_repetition_mixed_forms_plans_and_empty_answers(ending):
    assert analyze(trace(turn(finish=ending), final_value='7'))['detectors']['D15'] is False


def test_finish_in_code_is_ignored_and_final_literal_can_match_printed_computation():
    value = trace(turn('answer = 2 + 3\nprint(answer)\nnote = "FINAL(wrong)"', stdout='5\n', finish='FINAL(5)'), final_value='5')
    result = analyze(value)
    assert result['detectors']['D15'] is True
    assert result['detectors']['D14'] is True


def test_refinement_needs_count_evidence_and_checks_many_hit_boundary():
    def searches(output):
        return trace(turn('import re\nhits = re.findall("x", context)\nprint(len(hits))', stdout=output), turn('hits = re.findall("x", context)'))
    assert analyze(searches('4\n'))['detectors']['D4'] is False
    assert analyze(searches('3\n'))['detectors']['D4'] is True
    assert analyze(searches('uninterpretable\n'))['detectors']['D4'] is None


def test_failed_or_missing_runtime_call_evidence_cannot_be_a_positive_chunk_result():
    value = trace(turn('answer = llm_query(context[:20])', calls=[20]))
    value['turns'][0]['subcalls'][0]['error'] = 'max_subcalls exceeded'
    assert analyze(value)['detectors']['D8'] is False
    value['turns'][0]['subcalls'] = []
    assert analyze(value)['detectors']['D8'] is None


def test_no_mutation_and_config_requires_explicit_thresholds():
    from rlm_opsd.detectors import DetectorConfig

    value = trace(turn(P)); original = copy.deepcopy(value)
    analyze(value)
    assert value == original
    with pytest.raises(ValueError):
        DetectorConfig()
    with pytest.raises(ValueError):
        DetectorConfig.from_yaml('configs/detectors.yaml')
    with pytest.raises(ValueError):
        DetectorConfig(**{**THRESHOLDS, 'dense_coverage_min': 2})


def test_wrapping_context_in_a_prompt_does_not_hide_oversized_whole_call():
    value = trace(turn('answer = llm_query("Summarize: " + context)', calls=[111], finish='FINAL(done)'),tags=['small_context'])
    result = analyze(value)
    assert result['detectors']['D8'] is False
    assert result['task_tag_match'] is False


def test_constant_false_comprehension_does_not_create_calls_or_coverage():
    value = trace(turn('unused = [llm_query(context) for i in range(2) if False]\n'
                       'answer = llm_query(context[:20])', calls=[20]))
    result = analyze(value)
    assert result['detectors']['D9'] is False
    assert result['detectors']['D8'] is True
    assert result['detectors']['D18'] == 0.2


def test_subcall_search_window_is_a_read_and_verifies_used_hit():
    value = trace(turn('pos = context.find("x")'),
        turn('answer = llm_query(context[pos:pos+20])', calls=[20], finish='FINAL_VAR(answer)'),
        final_type='FINAL_VAR', final_value='yes', tags=['sparse'])
    result = analyze(value)
    assert result['detectors']['D5'] is True
    assert result['detectors']['D7'] is True
    assert result['task_tag_match'] is True


def test_dynamic_branch_never_proves_a_clean_dump_or_full_coverage():
    result = analyze(trace(turn('if unknown_flag:\n    print(context)')))
    assert result['detectors']['D2'] is None
    assert result['detectors']['D18'] is None
    assert result['unknown_reasons']


def test_iteration_and_membership_search_facts_on_list_context():
    value = trace(turn('hits = [i for i,d in enumerate(context) if "needle" in d]'))
    value['context_metadata'] = dict(context_type='list',context_total_length=100,context_lengths=[40,60])
    result = analyze(value)
    assert result['detectors']['D18'] == 1.0
    assert result['detectors']['D19'] == 'regex_filter'
    assert result['facts'][0]['searches']
    assert any(e['kind'] == 'iteration' for e in result['facts'][0]['accesses'])


def test_runtime_syntax_error_and_truncation_counts():
    value = trace(turn('exec("for:")',stdout='SyntaxError: invalid syntax\n',error='SyntaxError'),turn('print(context)', stdout='abc\n[truncated: full output length 100 chars]'))
    result = analyze(value)
    assert result['counts']['syntax_error_blocks'] == 1
    assert result['counts']['truncation_events'] == 1
    assert result['detectors']['D16'] == 0.5


def test_budget_failure_before_the_next_code_block_is_not_successful_coverage():
    value = trace(turn('raise ValueError("stop")\nprint(context)'))
    result = analyze(value)
    assert result['detectors']['D18'] != 1.0


def test_rebinding_context_to_a_literal_clears_original_geometry():
    result = analyze(trace(turn('context = "tiny"\nprint(context)')))
    assert result['detectors']['D2'] is True
    assert result['detectors']['D18'] == 0.0


@pytest.mark.parametrize('expression', ['context[:]', 'context[0:100]', 'f"Summarize: {context}"'])
def test_full_context_transformations_keep_whole_provenance(expression):
    value = trace(turn(f'out=llm_query({expression})',calls=[110],finish='FINAL(done)'),tags=['small_context'])
    result = analyze(value)
    assert result['detectors']['D8'] is False
    assert result['task_tag_match'] is False


@pytest.mark.parametrize('code', ['def dump():\n    print(context)\ndump()', 'len = print\nlen(context)'])
def test_unsupported_helpers_and_shadowed_builtins_cannot_prove_passes(code):
    result = analyze(trace(turn(P+'\n'+code,finish='FINAL(done)'),tags=['large_context']))
    assert result['task_tag_match'] is not True
    assert result['unknown_reasons']


def test_pattern_refinement_compares_values_not_variable_names():
    changed = trace(turn('import re\np="x"\nh=re.findall(p,context)\nprint(len(h))', stdout='0\n'),turn('p="y"\nh=re.findall(p,context)'))
    same = trace(turn('import re\nx="same"\nh=re.findall(x,context)\nprint(len(h))', stdout='0\n'),turn('y="same"\nh=re.findall(y,context)'))
    assert analyze(changed)['detectors']['D4'] is True
    assert analyze(same)['detectors']['D4'] is False


def test_unknown_oversized_call_cannot_pass_universal_tag_constraint():
    result = analyze(trace(turn('if context.startswith("x"):\n    out=llm_query(context)',calls=[100],finish='FINAL(done)'), tags=['small_context']))
    assert result['task_tag_match'] is None


def test_runtime_error_cannot_prove_later_code_executed():
    value = trace(turn('missing_name()\nprint(context)',stdout='NameError: missing_name', error='NameError'))
    result = analyze(value)
    assert result['detectors']['D18'] is None
    assert result['coverage_lower_bound'] == 0.0


def test_call_facts_include_logged_sizes_and_iteration_context():
    result = analyze(trace(turn('results = [llm_query(context[i:i+20]) for i in range(0,100,20)]',calls=[20]*5)))
    assert result['detectors']['D9'] is True
    assert result['detectors']['D11'] is True
    assert result['detectors']['D18'] == 1.0
    facts = result['facts'][0]['subcalls']
    assert all(f['prompt_chars'] == [20] for f in facts)


def test_position_metadata_is_not_dumped_context_or_a_chunk_prompt():
    result = analyze(trace(turn('pos = context.find("x")\nprint(pos)')))
    assert result['detectors']['D2'] is True
    result = analyze(trace(turn('pos = context.find("x")\nout = llm_query(str(pos))', calls=[2])))
    assert result['detectors']['D8'] is False


def test_repeated_provenance_is_canonical_and_bounded():
    from rlm_opsd.detectors.facts import Extractor
    engine = Extractor(dict(context_type='str',context_total_length=100,context_lengths=[]))
    engine.block_facts('a=context\nfor i in range(16):\n    a=a+a',0)
    assert len(engine.env['a'].ranges) == 1
    assert engine.env['a'].ranges == ((0,100),)


def test_large_list_geometry_does_not_invent_character_slice_bounds():
    value = trace(turn('print(context[:10])'), length=2000)
    value['context_metadata'] = dict(context_type='list',context_total_length=2000,context_lengths=[1]*2000)
    result = analyze(value)
    assert result['detectors']['D18'] in (None,0.005)
    if result['detectors']['D18'] is None:
        assert result['coverage_lower_bound'] == 0


def test_very_long_code_is_bounded_before_parsing():
    result = analyze(trace(turn('x=1\n' * 10000)))
    assert result['unknown_reasons']


@pytest.mark.parametrize('plan', ['I am going to search the context and then return the answer.',
    'Next, I will search the context.', 'First, search the context, then aggregate the results.'])
def test_common_plan_only_finishes_are_rejected(plan):
    assert analyze(trace(turn(finish=f'FINAL({plan})'),final_value=plan))['detectors']['D15'] is False


def test_impossible_prompt_lengths_raise_a_validation_error():
    with pytest.raises(ValueError,match='prompt_chars'):
        analyze(trace(turn('x = llm_query(context[:20])',calls=[10**309])))


def test_definition_defaults_execute_at_definition_time_so_are_not_silently_ignored():
    result = analyze(trace(turn(P+'\ndef unused(arg=print(context)):\n    pass',finish='FINAL(done)'),tags=['large_context']))
    assert result['task_tag_match'] is not True
