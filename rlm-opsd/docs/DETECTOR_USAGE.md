# M4 behavior analysis

`analyze_trajectory(trace, config, *, task_metadata=None)` is a pure offline
function exported by `rlm_opsd.detectors`. It accepts a trajectory dictionary or
`EpisodeTrace`, and returns JSON-serializable `detectors` (D1–D19),
`task_tag_match`, `counts`, `facts`, `coverage_lower_bound`, `unknown_reasons`,
and task grouping metadata. Input data is not modified. Code is parsed, never
executed; no context contents or model endpoint are needed.

```python
from rlm_opsd.detectors import DetectorConfig, analyze_trajectory
config = DetectorConfig.from_yaml("my-detectors.yaml")
analysis = analyze_trajectory(trajectory, config)
```

Operational values in [configs/detectors.yaml](../configs/detectors.yaml) remain
required and unset. The test fixtures supply explicit small thresholds; those
are not recommended production or gate thresholds. Required keys are
`probe_max_chars`, `dump_threshold`, `read_threshold`, `many_hits`,
`subcall_max_chars`, `min_batch_chars`, `max_subcalls_expected`,
`hand_copy_min_chars`, and `dense_coverage_min`. Call-count limits use a mapping
keyed by task ID, falling back to family; a missing limit makes D10 unknown.
Dense coverage must be strictly greater than its configured threshold.

## Evidence and applicability

Boolean detectors return true, false, or null. Null means not applicable,
missing evidence, or unsupported analysis; it never satisfies a required tag.
Known violations dominate unknown requirements. D16 and D18 are fractions;
D19 is a category or null. Reports retain known/unknown denominators instead of
turning nulls into passes or measured failures.

Facts retain code, parse status, accesses, search patterns/count evidence,
subcall provenance, assignments, prior-turn reads, literals, and uncertainties.
The analyzer tracks aliases and reassignment in source order. Metadata-only
`len`/`type` and bounded structure inspection do not read the underlying text.
Searches include `re.search/match/fullmatch/findall/finditer/split`, string
`find/index/count/split/splitlines`, membership tests, and supported comprehension
filters. Search positions propagate through bounded windows; independent search
patterns do not count as chained search. Printed positions are metadata, not raw
context dumps. Constant-false branches and unused plain function bodies do not
create behavior evidence.

D4 associates a leading integer observation with a single, unambiguous
`print(len(search_result), ...)` in a single-block turn. Other output formats
remain unknown. Known pattern values, not variable spellings, determine whether
refinement changed the query. D7 requires provenance from the final answer back
to a checked hit; merely checking an unrelated search does not suffice.

Actual subcall counts and prompt lengths come only from logged calls. Facts
record `prompt_chars` and `runtime_alignment`; ordered sites are matched in
source order, or a single site can collect repeated logged calls. Ambiguous
multiple sites retain unknown alignment. Failed calls fail D8; missing calls do
not pass. Whole-context provenance survives aliases, full-range slices, prompt
concatenation and f-strings. An unresolved oversized call cannot satisfy the
universal prohibition. D10 reports counts including failed attempts.

D14 uses computed-variable provenance. Literal variable assignments alone do
not pass; a literal `FINAL` can match a single printed computed value. D15 uses
the harness's fence-aware finish parser, counts every outside-code finish
(including ignored suffix text), and checks the logged accepted finish. A valid
logged `FINAL_VAR` supplies runtime evidence that the variable existed. Plan-only
finish rejection is a documented English-prefix heuristic, not general semantic
understanding. It recognizes future-intent forms and initial procedural steps;
manual review remains necessary for other wording/languages.

D16 combines AST parse failures and runtime SyntaxError/IndentationError/TabError
observations without double-counting a block. Aggregated multi-block errors
whose location is unavailable make the rate unknown. D17 compares the next
block after each error with normalized failing code and checks that the same
error did not recur; a different new error is not treated as the same error.
No next block fails recovery; no errors makes recovery not applicable.

## Geometry and conservative limits

New harness traces optionally include `context_metadata` with only
`context_type`, `context_total_length`, and `context_lengths`, plus optional
`size_bucket`. String lengths are Unicode character counts. List lengths must
sum to total length. Neither raw context nor its prefix is added by these fields.
Legacy logs remain valid. Supply the same geometry through `task_metadata` when
needed; conflicting embedded/external geometry is rejected.

D18 unions context character ranges supplied to reads, searches, scans, and
subcalls. It measures input coverage, not how far a short-circuit search engine
or a model inspected the supplied text. Overlaps count once. Negative bounds
and list chunk offsets are normalized. Empty context has coverage zero.
Missing geometry makes exact coverage and its lower bound null. Unknown ranges
make exact coverage null while known ranges provide `coverage_lower_bound`;
a known complete union remains complete. Events from runtime-error turns are
excluded from the lower bound because the failing statement is not identified.

This is a bounded static analyzer, not a Python interpreter. It supports literal
containers/arithmetic, bounded range/list iterations and common provenance
operations. Dynamic branches, unresolved loops, arbitrary helpers, shadowed
callables, executable function defaults/decorators, exception/control transfers,
and unsupported calls are explicit uncertainties. Compiled regex objects and
arbitrary user-defined transformations are not interpreted. Uncertainties
suppress positive static detector claims; logged statistics and protocol facts
remain available. Unsupported cases should be reviewed using the linked source
trajectory, not treated as failed model behavior.

Analysis limits are 100,000 source characters per block, 20,000 AST nodes per
block, 50,000 interpretation steps per trajectory, and 1,024 materialized
iteration/collection items. They bound analysis work, not behavioral acceptance.
Ranges are canonical unions to prevent exponential provenance growth. A limit
produces unknown evidence. These limits are distinct from user-selected detector,
gate, and exit thresholds.

## Other M4 interfaces

- [Offline CLI and manifest](DETECTOR_CLI.md), including the executable fixture
  command. Add `--overwrite` to regenerate its existing report.
- [Report denominators and output rules](DETECTOR_REPORTS.md).
- [Token categories, offset mapping and supplied divergence summaries](DETECTOR_CATEGORIES.md).
- [Hand-labelled D1–D19 fixtures and regressions](../tests/test_detectors.py).

`make test-m4` runs M4 tests; `make test` also verifies earlier milestones and
installed dependency provenance. The [fixture report](logs/m4/fixture-report/behavior.md)
contains hand-authored trajectories only. No model KL, teacher gate, training,
checkpoint comparison, GPU run, or measured task success is produced by M4.
