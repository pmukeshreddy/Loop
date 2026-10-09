# Offline assistant token categories

`rlm_opsd.detectors.categories` implements DETECTORS §5 with three pure functions:

- `classify_text_spans(text)` returns a complete, merged partition of the text as
  `{start, end, category}` records.
- `classify_token_offsets(text, offsets)` returns one record for every supplied
  token, preserving its index and character offsets.
- `summarize_token_divergence(turns, *, metric_kind, top_k=10, context_chars=40)`
  aggregates supplied values. Each turn contains `turn_index`, `text`, `offsets`,
  and `values`. Turn indices must be unique nonnegative integers.

All offsets are half-open Unicode **character** positions in the exact assistant
text, not UTF-8 bytes or UTF-16 code units. No helper tokenizes text or changes
rollout IDs. The caller must obtain offsets when collecting the original tokens;
these helpers cannot recover trustworthy offsets by decoding and re-encoding a
rollout suffix.

## Lexical policy

Outside fenced blocks, text is prose, except direct `FINAL(...)` and
`FINAL_VAR(...)` call names. Quoted strings, inline Markdown code, comments, name
prefixes, attribute accesses, and declarations do not become protocol call names.
The payload and parentheses of a finish remain prose. This is a lexical category
assignment, not evidence that a finish is valid or that code executed.

Markdown backtick and tilde fences with at least three matching characters are
recognized, with at most three leading spaces. A closing fence must use the same
character and be at least as long as its opener. Fence lines, including their
newlines, are protocol only for `repl`; other fence lines are code. Unclosed
fences extend to the end of the text.

Bodies marked `repl`, `python`, `py`, or with no language use Python's `tokenize`
module. Comment tokens are `comment`; direct `llm_query`, `FINAL`, and `FINAL_VAR`
call identifiers are `protocol`; remaining body characters are `code`. Thus a
Python example can contain a protocol identifier without being an executable
REPL block. Other languages remain entirely code; their comments are not parsed
as Python. Bare API references and calls to an attribute named `llm_query` remain
code. Shadowed names are not resolved. Python tokenization errors preserve labels
from the reliable prefix and leave the remaining body as code. Indented Markdown
code blocks and full CommonMark parsing are outside this helper's scope.

## Token boundaries and special tokens

The largest character overlap assigns a token's category. Ties favor protocol,
comment, code, then prose. Records retain `category_chars` for all overlaps and
`status="boundary"` when multiple categories intersect the token. This avoids
turning a long prose token into protocol because it barely touches a marker.

Offset `(0, 0)` means a special token and yields `category=null`,
`status="special"`. Other empty, reversed, negative, out-of-range, noninteger,
or decreasing-start offsets raise `ValueError`. Duplicate and overlapping
intervals are accepted and counted independently: multiple tokenizer pieces can
refer to the same Unicode character. Special offsets can occur anywhere without
resetting the preceding non-special start. Gaps in offsets are permitted; only
supplied tokens contribute to summaries.

## Divergence is supplied, never computed here

`metric_kind="full_kl"` means the caller asserts that each value is a
full-distribution KL divergence. Values must be finite and nonnegative. This
validation cannot prove how the caller obtained the values or which KL direction
was used.

`metric_kind="sampled_logprob_delta"` accepts signed finite values. The caller
must retain the subtraction convention with its source data. These values are
not reported as full KL. Top positions use the largest signed value, not the
largest absolute value.

Results include `source="caller_supplied"`, token-weighted count/sum/mean overall,
for each category and each turn, and `excluded_special_tokens`. Empty means are
`null`. Special offsets never enter means or top positions, but their supplied
values must still be valid. `top_positions` includes turn/token indices,
category, original offsets, value, token text, and clipped context with character
bounds. Ties sort by turn index then token index.

Handwritten fixtures and synthetic values are covered by
[the category tests](../tests/test_detector_categories.py). Test-first evidence
is recorded in [initial red](logs/m4/categories-red.log),
[initial green](logs/m4/categories-green.log),
[Unicode regression red](logs/m4/categories-unicode-red.log), and
[Unicode regression green](logs/m4/categories-unicode-green.log).
Installed source paths, signatures, and hashes are in
[the API log](logs/m4/categories-api.log). A cached Qwen tokenizer was exercised
on a standalone fixture in [the offset smoke log](logs/m4/categories-tokenizer-smoke.log).
No model weights, model inference, logprob evaluation, or model KL run was used.
