# Offline behavior reports

`rlm_opsd.detectors.reports` implements DETECTORS §4 for supplied analysis
records. It does not run models, score correctness, apply gate thresholds, or
perform evaluation sweeps.

```python
from rlm_opsd.detectors.reports import write_behavior_report

paths = write_behavior_report(
    records,
    "reports/my-run",
    source_label="Supplied trajectory analyses; no new model runs",
)
```

Each input record contains `phase` (`before`, `teacher`, or `after`),
`trajectory_path` (an existing file), and `analysis` from `analyze_trajectory`.
An optional `task_success` must be an explicitly supplied boolean. Omission
means unmeasured success. For hand-labelled fixtures, pass a source label such
as `Hand-labelled fixtures; not model results` and label the input files too.
Do not use fixture reports as evidence of model behavior.

The return value maps `markdown` and `csv` to their output `Path` objects.
`aggregate_behavior(records)` returns the same metrics as long-form dictionaries
without writing files. The iterable is consumed once. Duplicate resolved source
paths are rejected, including reuse across phases; separate rollout files for
the same task are allowed.

Each phase has an overall group and separate breakdowns by family, size bucket,
and domain. Groups observed in any phase appear in every phase; missing groups
are marked `not run`. Missing metadata uses the label `unknown`, distinct from
the size bucket `0`.

CSV rows contain the phase, grouping dimension and label, metric ID and name,
category, status, value, numerator, denominator, known/unknown trajectory counts,
total trajectory count, and a JSON list of absolute source paths. Markdown
links each metric row to its group's source-file links. Source lists include
unknown records because these contribute the unknown count.

- Boolean detector rates and `task_tag_match` exclude unknown values from their
  denominators; known false values remain measured failures.
- D16 pools syntax-error blocks over code blocks from trajectories with known
  syntax evidence. It does not average per-trajectory rates.
- D18 is the mean exact coverage across known trajectories. The mean
  `coverage_lower_bound` is separate and must not be interpreted as exact
  coverage.
- D19 reports each category's count and proportion over known categories.
- `subcall_count` is the total; `subcall_mean_count` is the mean per trajectory.
  Prompt-character means weight each supplied trajectory mean by its actual
  subcall count; maxima use the supplied call maxima. Empty-call trajectories
  contribute no prompt samples. Truncation events are summed.
- `task_success` uses only explicitly supplied success labels and is tracked,
  never optimized or inferred from detector passes.

`known` and `unknown` count trajectories, while `denominator` uses the metric's
units: trajectories, code blocks, or subcalls. Sum metrics have no denominator.
`partial` means the value uses available evidence with other records unknown.
`unknown` means no usable evidence was supplied; `no observations` means known
zero code blocks or subcalls supplied no rate or prompt sample. `not run`
means no trajectories exist for that phase/group, and its value, numerator,
and denominator are blank. CSV blanks and Markdown dashes are never zeroes.

Inputs with nonfinite numbers, invalid types, inconsistent syntax-error rates,
or impossible prompt and coverage summaries are rejected. All validation and
rendering happens before writes. Existing output files are refused by default.
`overwrite=True` accepts only a complete prior report with this writer's
marker/header; unrelated files, source trajectories, and output symlinks are
protected. Replacements are atomic per file, not transactional across the pair.
