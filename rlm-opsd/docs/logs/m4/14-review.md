# M4 read-only review record

A separate reviewer inspected the M4 detector, category, report, and metadata
code against the spec. The review used the untracked in-place source tree;
there is no meaningful base/head commit diff. Reproductions were offline and
used hand-authored trajectories. No model performance was reviewed.

Findings and fixes:

- Whole-context prompt wrappers and full-range slices lost whole provenance.
  Propagate whole provenance through combinations and recognize full ranges.
- Unsupported helpers/shadowed builtin names could silently pass D1/D2.
  Mark unsupported callables and executable definition defaults as uncertain.
- An unknown oversized call could pass the universal tag constraint.
  Preserve unknown until whole-context prohibition is resolved.
- D4 compared AST variable spellings rather than known pattern values.
  Compare known values; unknown values cannot establish changed patterns.
- Range provenance doubled on repeated concatenation despite the step limit.
  Canonicalize unions, bound materialized items/source/AST/step work.
- Common plan-only FINAL text passed the narrow prefix heuristic.
  Cover the reproduced future-intent/initial-step forms; document heuristic scope.
- Impossible prompt sizes could overflow means. Validate prompt_chars against
  Python's representable string length before computing statistics.

The parent also regression-tested constant-false comprehensions, content reads
inside subcalls, iteration facts, runtime-error coverage, scalar search positions,
and logged prompt sizes in per-block facts. Each identified failure was retained
in red logs and followed by a passing run. See 03–10 logs and the full suite in
11-full-suite.log. No finding in token categories, reports or trajectory metadata
required a review fix. Unsupported arbitrary Python remains a documented unknown,
not a promise of complete runtime reconstruction.

Closure: the reviewer reran the exact seven reported reproductions against the
final source and confirmed each was resolved. The closure was read-only and did
not broaden scope.
