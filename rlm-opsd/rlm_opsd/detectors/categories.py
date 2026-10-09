"""Offline lexical categories and summaries of caller-supplied divergence.

Offsets are half-open Python Unicode character positions in one assistant turn.
This module never encodes text, changes rollout token IDs, or scores a model.
"""

from collections.abc import Mapping, Sequence
from io import StringIO
import math
import re
import tokenize


CATEGORIES = ('prose', 'code', 'comment', 'protocol')
_PRIORITY = {name: rank for rank, name in enumerate(CATEGORIES)}
_FENCE = re.compile(r' {0,3}(`{3,}|~{3,})([^\r\n]*)')
_INLINE_CODE = re.compile(r'(`+)(.*?)\1')
_PROTOCOL_NAMES = frozenset({'FINAL', 'FINAL_VAR', 'llm_query'})
_SKIP_TOKENS = frozenset({tokenize.NL, tokenize.INDENT,
                         tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER})


def _lexical_spans(source: str, *, in_code: bool) -> list[tuple[int, int, str]]:
    """Retain reliable tokenization before an error; never regex-scan its tail."""
    line_starts = [0]
    for line in StringIO(source):
        line_starts.append(line_starts[-1] + len(line))

    def offset(position: tuple[int, int]) -> int:
        row, column = position
        return line_starts[min(row - 1, len(line_starts) - 1)] + column

    tokens = []
    uncertain_line = None
    try:
        for item in tokenize.generate_tokens(StringIO(source).readline):
            # Older Python tokenizers can yield an unmatched quote as ERRORTOKEN
            # then NAMEs within that malformed string. Do not call them protocol.
            if item.type == tokenize.ERRORTOKEN and item.string in {'\'', '"'}:
                uncertain_line = item.start[0]
            if uncertain_line == item.start[0]:
                continue
            tokens.append(item)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    spans = []
    if in_code:
        spans.extend((offset(item.start), offset(item.end), 'comment')
                     for item in tokens if item.type == tokenize.COMMENT)
    significant = [item for item in tokens if item.type not in _SKIP_TOKENS]
    for index, item in enumerate(significant):
        if item.type != tokenize.NAME or item.string not in _PROTOCOL_NAMES:
            continue
        if not in_code and item.string == 'llm_query':
            continue
        previous = significant[index - 1].string if index else None
        following = significant[index + 1].string if index + 1 < len(significant) else None
        if following == '(' and previous not in {'.', 'def', 'class'}:
            spans.append((offset(item.start), offset(item.end), 'protocol'))
    return spans


def classify_text_spans(text: str) -> list[dict]:
    """Partition text into contiguous prose/code/comment/protocol spans.

    Fenced bodies are code. Python, py, repl and unlabelled bodies use Python's
    tokenizer for comments and direct protocol call names. Other languages stay
    code. Only repl fence lines themselves are protocol. Outside fences only
    direct FINAL/FINAL_VAR call names are protocol; quoted/inline-code mentions
    remain prose. This is lexical classification, not execution or finish proof.
    Unclosed fences extend to EOF; malformed Python retains its reliable prefix.
    """
    if not isinstance(text, str):
        raise ValueError('text must be a string')
    labels = ['prose'] * len(text)

    def paint(start: int, end: int, category: str) -> None:
        labels[start:end] = [category] * (end - start)

    def lex(start: int, end: int, *, in_code: bool) -> None:
        for left, right, category in _lexical_spans(text[start:end], in_code=in_code):
            paint(start + left, start + right, category)

    opened = None
    body_start = 0
    position = 0
    for line in StringIO(text):
        end = position + len(line)
        candidate = _FENCE.fullmatch(line.rstrip('\r\n'))
        if opened is None and candidate:
            marker, info = candidate.groups()
            # A backtick in an info string does not open a Markdown fence.
            if marker[0] != '`' or '`' not in info:
                language = info.strip().split(maxsplit=1)[0] if info.strip() else ''
                opened = (marker, language.lower())
                body_start = end
                paint(position, end, 'protocol' if opened[1] == 'repl' else 'code')
                position = end
                continue
        if opened is not None:
            marker, language = opened
            is_close = (candidate is not None and candidate.group(1)[0] == marker[0]
                        and len(candidate.group(1)) >= len(marker)
                        and not candidate.group(2).strip())
            if is_close:
                if language in {'', 'repl', 'python', 'py'}:
                    lex(body_start, position, in_code=True)
                paint(position, end, 'protocol' if language == 'repl' else 'code')
                opened = None
            else:
                paint(position, end, 'code')
        else:
            # Isolate prose lines so punctuation/indentation on an earlier line
            # cannot hide a later finish marker. Mask Markdown inline code first.
            masked = _INLINE_CODE.sub(lambda match: ' ' * len(match.group()), line)
            for left, right, category in _lexical_spans(masked, in_code=False):
                paint(position + left, position + right, category)
        position = end
    if opened is not None and opened[1] in {'', 'repl', 'python', 'py'}:
        lex(body_start, len(text), in_code=True)

    result = []
    start = 0
    for index in range(1, len(text) + 1):
        if index == len(text) or labels[index] != labels[start]:
            result.append(dict(start=start, end=index, category=labels[start]))
            start = index
    return result


def classify_token_offsets(text: str, offsets: Sequence[Sequence[int]]) -> list[dict]:
    """Assign one category to each supplied token interval without tokenization.

    (0, 0) denotes a special token: category=None. Other empty, out-of-range or
    noninteger intervals are errors. Non-special starts must be nondecreasing;
    overlapping/duplicate intervals (e.g. byte pieces of Unicode) stay separate.
    Mixed tokens use maximum character overlap; ties favor protocol, comment,
    code, then prose. ``category_chars`` and ``status`` preserve that ambiguity.
    """
    spans = classify_text_spans(text)
    result = []
    previous_start = -1
    for index, interval in enumerate(offsets):
        if (not isinstance(interval, (tuple, list)) or len(interval) != 2
                or any(type(value) is not int for value in interval)):
            raise ValueError(f'offset {index} must contain two integer character positions')
        start, end = interval
        if start == end == 0:
            result.append(dict(token_index=index, start=0, end=0, category=None,
                               status='special', category_chars={}))
            continue
        if not 0 <= start < end <= len(text) or start < previous_start:
            raise ValueError(f'offset {index} is empty, out of range, or out of order')
        previous_start = start
        counts = {}
        for span in spans:
            overlap = min(end, span['end']) - max(start, span['start'])
            if overlap > 0:
                category = span['category']
                counts[category] = counts.get(category, 0) + overlap
        category = max(counts, key=lambda name: (counts[name], _PRIORITY[name]))
        result.append(dict(token_index=index, start=start, end=end, category=category,
                           status='boundary' if len(counts) > 1 else 'ok', category_chars=counts))
    return result


def _stats(values: Sequence[float]) -> dict:
    total = math.fsum(values)
    return dict(count=len(values), sum=total, mean=total / len(values) if values else None)


def summarize_token_divergence(
        turns: Sequence[Mapping], *, metric_kind: str, top_k: int = 10,
        context_chars: int = 40) -> dict:
    """Summarize aligned supplied values; this function never computes model KL.

    Each turn supplies ``turn_index``, ``text``, ``offsets`` and ``values``.
    ``full_kl`` asserts the caller supplied nonnegative full-distribution KL.
    ``sampled_logprob_delta`` accepts signed values; callers must record their
    subtraction convention. All values, including special tokens, must be finite.
    Means weight tokens equally. Special offsets are excluded, duplicate offsets
    retained. Top positions sort by signed value descending, then turn/token index.
    """
    if metric_kind not in {'full_kl', 'sampled_logprob_delta'}:
        raise ValueError('metric_kind must be full_kl or sampled_logprob_delta')
    if type(top_k) is not int or top_k < 0:
        raise ValueError('top_k must be a nonnegative integer')
    if type(context_chars) is not int or context_chars < 0:
        raise ValueError('context_chars must be a nonnegative integer')
    category_values = {category: [] for category in CATEGORIES}
    all_values = []
    by_turn = []
    positions = []
    excluded = 0
    seen_turns = set()
    for turn in turns:
        turn_index = turn['turn_index']
        if type(turn_index) is not int or turn_index < 0 or turn_index in seen_turns:
            raise ValueError('turn_index must be a unique nonnegative integer')
        seen_turns.add(turn_index)
        text, offsets, values = turn['text'], turn['offsets'], turn['values']
        classified = classify_token_offsets(text, offsets)
        if len(classified) != len(values):
            raise ValueError('values must align one-to-one with token offsets')
        turn_values = []
        for token, raw_value in zip(classified, values, strict=True):
            if (type(raw_value) not in {int, float} or not math.isfinite(raw_value)
                    or (metric_kind == 'full_kl' and raw_value < 0)):
                raise ValueError('values must be finite numbers; full_kl must be nonnegative')
            value = float(raw_value)
            if token['category'] is None:
                excluded += 1
                continue
            category_values[token['category']].append(value)
            all_values.append(value)
            turn_values.append(value)
            start, end = token['start'], token['end']
            left, right = max(0, start - context_chars), min(len(text), end + context_chars)
            positions.append(dict(turn_index=turn_index, token_index=token['token_index'],
                                  value=value, category=token['category'], start=start, end=end,
                                  status=token['status'], token_text=text[start:end],
                                  context_start=left, context_end=right, context=text[left:right]))
        by_turn.append(dict(turn_index=turn_index, **_stats(turn_values)))
    positions.sort(key=lambda item: (-item['value'], item['turn_index'], item['token_index']))
    return dict(metric_kind=metric_kind, source='caller_supplied', overall=_stats(all_values),
                by_category={category: _stats(values) for category, values in category_values.items()},
                by_turn=sorted(by_turn, key=lambda item: item['turn_index']),
                excluded_special_tokens=excluded, top_positions=positions[:top_k])
