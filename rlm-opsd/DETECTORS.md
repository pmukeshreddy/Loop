# DETECTORS: verifying RLM behavior

Detectors are pure functions over a trajectory log (SPEC §2.6). They parse each code block with Python's `ast` and the observations, then emit per-trajectory booleans and counts. Thresholds come from `configs/detectors.yaml`.

## 1. Per-turn facts (extracted first)

For each code block, record:
- **Parse result:** OK, or `SyntaxError`.
- **Accesses to `context`:** `len`, `type`, iteration, slices with bounds, and `print` of `context` or of a slice.
- **Search ops:** `re.*`, `str.find/index/count/split`, `in`, and comprehension filters over `context`.
- **`llm_query` calls:** argument provenance (slice, chunk variable, search result, or the whole `context`), whether the call is inside a loop or comprehension, and prompt size in chars (from the sub-call log).
- **Variables:** assignments, and which earlier-turn variables are read.
- **Literals:** long string and number literals.

## 2. Detectors

| ID | Name | Passes when |
|---|---|---|
| D1 | `probe_first` | The first code that touches `context` uses only `len` / `type` / structure inspection / slices ≤ `probe_max_chars` |
| D2 | `no_raw_dump` | No print of `context`, and no print of a slice > `dump_threshold`. Truncation events are counted. |
| D3 | `code_search_before_read` | On `sparse` tasks, a search op happens before the first content read > `read_threshold` |
| D4 | `search_refinement` | After a search whose output shows 0 hits or > `many_hits`, the next search uses a different pattern |
| D5 | `windowed_reads` | Content reads are slices around positions produced by search (position ± window) |
| D6 | `chained_search` | A search pattern is built from a variable assigned from an earlier search result |
| D7 | `verify_hit` | A hit used in the answer was checked (window read or `llm_query` on the snippet) before the finish |
| D8 | `subcalls_on_chunks` | `llm_query` arguments come from slices, chunks, or matches. A whole-context call fails unless it fits in `subcall_max_chars`. |
| D9 | `subcalls_in_loop` | `llm_query` is called inside a loop or comprehension |
| D10 | `batching_ok` | Sub-call count ≤ `max_subcalls_expected(task)`, and mean prompt chars ≥ `min_batch_chars`. The count, mean, and max are reported. |
| D11 | `buffer_store` | `llm_query` results are assigned or appended to variables |
| D12 | `vars_reused` | A variable defined in turn i is read in a turn j > i |
| D13 | `no_hand_copy` | No long literal in code appears verbatim in an earlier observation |
| D14 | `aggregate_in_code` | The final answer derives from computed variables (`FINAL_VAR`, or `FINAL` with a value computed in the REPL) |
| D15 | `clean_finish` | Exactly one finish; `FINAL_VAR` names an existing variable; no mixed forms; the finish text is not a plan or a description of future steps |
| D16 | `syntax_error_rate` | Number: failed parses or `SyntaxError` observations / code blocks |
| D17 | `error_recovery` | After a traceback, the next block changes the failing code and the same error does not repeat |
| D18 | `coverage` | Number: the fraction of context chars that passed through a sub-call, search, or scan op (from slice bounds) |
| D19 | `first_decomposition` | Category of the first non-probe action: `direct_read`, `regex_filter`, `chunk_subcall`, `whole_subcall`, or `other` |

## 3. Tags to required detectors

| Task tag | Required | Forbidden |
|---|---|---|
| `large_context` | D1, D2 | — |
| `sparse` | D3, D5, D7 | — |
| `chained_search` | D6 | — |
| `dense` / `needs_subcalls` | D8, D9, D10, D11, D18 above `dense_coverage_min` | — |
| `aggregate_in_code` | D14 | — |
| `output_in_variable` | `FINAL_VAR` used | — |
| `small_context` | — | Decomposition is not required; a direct read is allowed |
| (all tasks) | D15, D17 when errors occur | Whole-context sub-call over the size limit |

`task_tag_match` passes when every required detector for the task's tags passes and no forbidden pattern occurs.

## 4. Reports

**Three-way comparison** on `dev_behavior`:
- `before`: base model with x
- `teacher`: base model with y\*
- `after`: checkpoint with x

**Breakdown:** per family, size bucket, and domain. Report every detector rate, `task_tag_match`, the syntax-error rate, sub-call stats, the D19 distribution, and task success (tracked only).

**Output:** `reports/<run_id>/behavior.md` and `behavior.csv`. Every number links to its trajectory logs.

## 5. Token-category KL

**Categories:**
- Classify each root assistant token span as `prose`, `code`, `comment` (inside code), or `protocol` (`FINAL`, `FINAL_VAR`, `llm_query`, and repl fences).
- Map spans to tokens using offsets from the tokenizer.

**Report:**
- Mean teacher–student KL per category.
- Mean KL per turn index.
- The top-K highest-KL positions with surrounding text, for manual review.

## 6. Tests

Write hand-made fixture trajectories with known labels for every detector: one that should pass and one that should fail. Detectors must match the labels exactly.
