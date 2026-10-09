"""Hand-labelled text, offsets, and synthetic divergence; no model runs."""

import math

import pytest


def test_text_spans_cover_prose_code_comments_and_protocol_with_exact_offsets():
    from rlm_opsd.detectors.categories import classify_text_spans

    # Hand-counted: prose 0:3, opener 3:11, code 11:15, comment 15:19,
    # newline 19:20, closer 20:24, finish identifier 24:29, answer 29:32.
    text = "Hi\n```repl\nx=1 # ok\n```\nFINAL(7)"
    assert classify_text_spans(text) == [
        {"start": 0, "end": 3, "category": "prose"},
        {"start": 3, "end": 11, "category": "protocol"},
        {"start": 11, "end": 15, "category": "code"},
        {"start": 15, "end": 19, "category": "comment"},
        {"start": 19, "end": 20, "category": "code"},
        {"start": 20, "end": 29, "category": "protocol"},
        {"start": 29, "end": 32, "category": "prose"},
    ]


@pytest.mark.parametrize("text,want", [
    ("We should search. # ordinary prose", [("prose", "We should search. # ordinary prose")]),
    ("FINAL(7)", [("protocol", "FINAL"), ("prose", "(7)")]),
    ("FINAL_VAR(answer)", [("protocol", "FINAL_VAR"), ("prose", "(answer)")]),
    ("FINALITY(x) FINAL llm_query(x)", [("prose", "FINALITY(x) FINAL llm_query(x)")]),
    ("'FINAL(x)' `FINAL_VAR(x)`", [("prose", "'FINAL(x)' `FINAL_VAR(x)`")]),
    ("# FINAL(x) is mentioned", [("prose", "# FINAL(x) is mentioned")]),
    ("", []),
])
def test_prose_and_finish_identifiers_have_positive_and_negative_labels(text, want):
    from rlm_opsd.detectors.categories import classify_text_spans

    assert [(s["category"], text[s["start"]:s["end"]])
            for s in classify_text_spans(text)] == want


def test_python_tokenization_ignores_api_names_inside_strings_comments_and_attributes():
    from rlm_opsd.detectors.categories import classify_text_spans

    text = ('```repl\n'
            'x = "llm_query(ctx) # FINAL(x)"\n'
            '# llm_query(ctx) FINAL_VAR(x)\n'
            'y = llm_query(ctx)\n'
            'obj.llm_query(ctx)\n'
            'def FINAL(x): pass\n'
            '```\n')
    spans = classify_text_spans(text)
    assert [(s["category"], text[s["start"]:s["end"]]) for s in spans] == [
        ("protocol", "```repl\n"),
        ("code", 'x = "llm_query(ctx) # FINAL(x)"\n'),
        ("comment", '# llm_query(ctx) FINAL_VAR(x)'),
        ("code", '\ny = '),
        ("protocol", 'llm_query'),
        ("code", '(ctx)\nobj.llm_query(ctx)\ndef FINAL(x): pass\n'),
        ("protocol", '```\n'),
    ]


@pytest.mark.parametrize("text,want", [
    ('```python\nx = 1 # yes\n```\n', [
        ('code', '```python\nx = 1 '), ('comment', '# yes'), ('code', '\n```\n')]),
    ('```javascript\n// llm_query(ctx) # text\nFINAL(7)\n```', [
        ('code', '```javascript\n// llm_query(ctx) # text\nFINAL(7)\n```')]),
    ('~~~repl\nllm_query(ctx)\n~~~\n', [
        ('protocol', '~~~repl\nllm_query'), ('code', '(ctx)\n'), ('protocol', '~~~\n')]),
    ('````repl\n```\n# still inside\n````\nDone', [
        ('protocol', '````repl\n'), ('code', '```\n'), ('comment', '# still inside'),
        ('code', '\n'), ('protocol', '````\n'), ('prose', 'Done')]),
    ('```repl\nx = 1 # comment', [
        ('protocol', '```repl\n'), ('code', 'x = 1 '), ('comment', '# comment')]),
])
def test_markdown_fences_do_not_turn_non_python_content_into_python_protocol(text, want):
    from rlm_opsd.detectors.categories import classify_text_spans

    assert [(s["category"], text[s["start"]:s["end"]])
            for s in classify_text_spans(text)] == want


@pytest.mark.parametrize("source,want_protocol,want_comments", [
    ('x = (\n# valid comment before incomplete call\nllm_query(ctx)', ['llm_query'],
     ['# valid comment before incomplete call']),
    ('x = "llm_query(ctx)\n', [], []),
    ('x = """llm_query(ctx)\n# inside unclosed string', [], []),
    ('x = """# not a comment\nllm_query(ctx)"""\n# comment', [], ['# comment']),
])
def test_malformed_python_preserves_known_lexical_labels_without_inventing_protocol(
        source, want_protocol, want_comments):
    from rlm_opsd.detectors.categories import classify_text_spans

    text = '```repl\n' + source
    spans = classify_text_spans(text)
    assert [text[s['start']:s['end']] for s in spans if s['category'] == 'protocol'] == [
        '```repl\n', *want_protocol]
    assert [text[s['start']:s['end']] for s in spans if s['category'] == 'comment'] == want_comments


def test_unicode_offsets_and_duplicate_intervals_preserve_supplied_token_positions():
    from rlm_opsd.detectors.categories import classify_token_offsets

    assert classify_token_offsets('é🦉 FINAL(好)', [(0, 1), (1, 2), (1, 2), (3, 8), (9, 10)]) == [
        dict(token_index=0, start=0, end=1, category='prose', status='ok', category_chars={'prose': 1}),
        dict(token_index=1, start=1, end=2, category='prose', status='ok', category_chars={'prose': 1}),
        dict(token_index=2, start=1, end=2, category='prose', status='ok', category_chars={'prose': 1}),
        dict(token_index=3, start=3, end=8, category='protocol', status='ok', category_chars={'protocol': 5}),
        dict(token_index=4, start=9, end=10, category='prose', status='ok', category_chars={'prose': 1}),
    ]


def test_unicode_line_separator_inside_python_string_does_not_shift_later_offsets():
    from rlm_opsd.detectors.categories import classify_text_spans

    text = '```repl\ns = "a\u2028b"\n# next\nllm_query(s)\n```'
    assert [(s['category'], text[s['start']:s['end']])
            for s in classify_text_spans(text)] == [
        ('protocol', '```repl\n'), ('code', 's = "a\u2028b"\n'),
        ('comment', '# next'), ('code', '\n'), ('protocol', 'llm_query'),
        ('code', '(s)\n'), ('protocol', '```'),
    ]


def test_bare_api_reference_on_previous_statement_is_not_a_call():
    from rlm_opsd.detectors.categories import classify_text_spans

    text = '```repl\nllm_query\n(context)\n```'
    assert [(s['category'], text[s['start']:s['end']])
            for s in classify_text_spans(text)] == [
        ('protocol', '```repl\n'), ('code', 'llm_query\n(context)\n'), ('protocol', '```')]


def test_boundary_tokens_use_majority_then_documented_tie_priority():
    from rlm_opsd.detectors.categories import classify_token_offsets

    assert classify_token_offsets('x FINAL(a)', [(0, 10), (6, 8), (0, 0)]) == [
        dict(token_index=0, start=0, end=10, category='protocol', status='boundary',
             category_chars={'prose': 5, 'protocol': 5}),
        dict(token_index=1, start=6, end=8, category='protocol', status='boundary',
             category_chars={'prose': 1, 'protocol': 1}),
        dict(token_index=2, start=0, end=0, category=None, status='special', category_chars={}),
    ]
    # A long prose token touching FINAL is prose, not protocol by mere intersection.
    assert classify_token_offsets('Words FINAL(abcdefgh)', [(0, 21)])[0]['category'] == 'prose'


@pytest.mark.parametrize('offsets', [
    [(-1, 1)], [(2, 1)], [(1, 1)], [(0, 4)], [(False, 1)], [(0, 1.5)],
    [(0,)], [(0, 1, 2)], ['ab'], [(1, 2), (0, 1)],
])
def test_invalid_offsets_raise_instead_of_silently_corrupting_token_alignment(offsets):
    from rlm_opsd.detectors.categories import classify_token_offsets

    with pytest.raises(ValueError, match='offset'):
        classify_token_offsets('abc', offsets)


def test_kl_summary_uses_token_weighted_means_by_category_turn_and_traceable_top_k():
    from rlm_opsd.detectors.categories import summarize_token_divergence

    turns = [
        dict(turn_index=0, text='Hi FINAL(7)', offsets=[(0, 2), (3, 8), (0, 0)], values=[1., 3., 99.]),
        dict(turn_index=2, text='```repl\nx # y\n```', offsets=[(8, 9), (10, 13), (14, 17)],
             values=[2., 6., 5.]),
    ]
    report = summarize_token_divergence(turns, metric_kind='full_kl', top_k=2, context_chars=2)
    assert report['metric_kind'] == 'full_kl'
    assert report['source'] == 'caller_supplied'
    assert report['overall'] == {'count': 5, 'sum': 17., 'mean': 3.4}
    assert report['by_category'] == {
        'prose': {'count': 1, 'sum': 1., 'mean': 1.},
        'code': {'count': 1, 'sum': 2., 'mean': 2.},
        'comment': {'count': 1, 'sum': 6., 'mean': 6.},
        'protocol': {'count': 2, 'sum': 8., 'mean': 4.},
    }
    assert report['by_turn'] == [
        {'turn_index': 0, 'count': 2, 'sum': 4., 'mean': 2.},
        {'turn_index': 2, 'count': 3, 'sum': 13., 'mean': 13. / 3.},
    ]
    assert report['excluded_special_tokens'] == 1
    assert report['top_positions'] == [
        dict(turn_index=2, token_index=1, value=6., category='comment', start=10, end=13,
             status='ok', token_text='# y', context_start=8, context_end=15, context='x # y\n`'),
        dict(turn_index=2, token_index=2, value=5., category='protocol', start=14, end=17,
             status='ok', token_text='```', context_start=12, context_end=17, context='y\n```'),
    ]


def test_signed_sampled_delta_stays_signed_and_is_not_named_kl():
    from rlm_opsd.detectors.categories import summarize_token_divergence

    report = summarize_token_divergence([
        dict(turn_index=1, text='abc', offsets=[(0, 1), (1, 2), (2, 3)], values=[-4., -1., 2.])
    ], metric_kind='sampled_logprob_delta', top_k=3, context_chars=0)
    assert report['metric_kind'] == 'sampled_logprob_delta'
    assert report['overall'] == {'count': 3, 'sum': -3., 'mean': -1.}
    assert [row['value'] for row in report['top_positions']] == [2., -1., -4.]
    assert [row['token_text'] for row in report['top_positions']] == ['c', 'b', 'a']


def test_empty_categories_turns_and_duplicate_unicode_tokens_have_honest_denominators():
    from rlm_opsd.detectors.categories import summarize_token_divergence

    report = summarize_token_divergence([
        dict(turn_index=0, text='', offsets=[(0, 0)], values=[0.]),
        dict(turn_index=1, text='🦉', offsets=[(0, 1), (0, 1)], values=[1., 3.]),
    ], metric_kind='full_kl', top_k=0)
    assert report['overall'] == {'count': 2, 'sum': 4., 'mean': 2.}
    assert report['by_category']['code'] == {'count': 0, 'sum': 0., 'mean': None}
    assert report['by_turn'][0] == {'turn_index': 0, 'count': 0, 'sum': 0., 'mean': None}
    assert report['top_positions'] == []
    empty = summarize_token_divergence([], metric_kind='full_kl')
    assert empty['overall'] == {'count': 0, 'sum': 0., 'mean': None}


@pytest.mark.parametrize('values', [[-1.], [math.nan], [math.inf], [True], ['1.0'], [], [1., 2.]])
def test_full_kl_rejects_negative_nonfinite_nonnumeric_or_misaligned_inputs(values):
    from rlm_opsd.detectors.categories import summarize_token_divergence

    with pytest.raises(ValueError):
        summarize_token_divergence([
            dict(turn_index=0, text='a', offsets=[(0, 1)], values=values),
        ], metric_kind='full_kl')


@pytest.mark.parametrize('kwargs', [
    {'metric_kind': 'kl'}, {'metric_kind': 'full_kl', 'top_k': -1},
    {'metric_kind': 'full_kl', 'top_k': True},
    {'metric_kind': 'full_kl', 'context_chars': -1},
])
def test_summary_rejects_ambiguous_metric_and_invalid_review_parameters(kwargs):
    from rlm_opsd.detectors.categories import summarize_token_divergence

    with pytest.raises(ValueError):
        summarize_token_divergence([], **kwargs)


def test_duplicate_turn_indices_are_rejected_to_keep_top_positions_unambiguous():
    from rlm_opsd.detectors.categories import summarize_token_divergence

    turn = dict(turn_index=0, text='a', offsets=[(0, 1)], values=[1.])
    with pytest.raises(ValueError, match='turn_index'):
        summarize_token_divergence([turn, turn], metric_kind='full_kl')
