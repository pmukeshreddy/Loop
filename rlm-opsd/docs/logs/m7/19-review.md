# M7 independent review and test-first closure

Reviewer `/root/m7_review` performed a read-only whole-feature review against
AGENTS.md, SPEC §6.1–6.5 and the M7 plan. No files or Git state were changed by
the reviewer. The project is untracked in its parent repository, so direct
file/source inspection was used rather than a fictitious commit range.

One P2 finding: `_token_losses` checked finite inputs before temperature
scaling/log-softmax. Inputs `[3e38, -3e38]` or ordinary logits at temperature
`1e-40` could still overflow FP32 normalization and return NaN loss/gradients.
The reviewer reproduced this in both dense and chunked APIs. Parent reproduced
the arithmetic stages in [11-overflow-investigation.log](11-overflow-investigation.log).

Four red regressions in [12-overflow-red.log](12-overflow-red.log) preceded
normalized-logprob validation. The same fix pass added two scalar-range
regressions ([14-scalar-red.log](14-scalar-red.log)): equal logits can hide
reciprocal-temperature overflow until backward, or produce NaN with an
unrepresentable gate slope. Working-precision scalar checks now reject these
settings before loss/gradient computation. No probability clamp or changed
expected loss was used to force a pass.

Closure evidence: [15-m7-final.log](15-m7-final.log) has 74 M7 tests passing;
[17-full-suite-final.log](17-full-suite-final.log) has 501 pytest tests and
3 M0 checks passing. Every substantive fix had a failing regression first.
No findings were deferred and no second reviewer/re-review was dispatched.

The reviewer found the remaining gradient detachment, frozen teacher behavior,
projection/backward memory lifetime, token normalization, factory/config
selection and objective evidence consistent with scope. Review limits were
explicit: no concurrent full-suite run by the reviewer, no pretrained/GPU
execution, and documentation was still being finished. Parent performed the
full suite and final documentation/link audit. GPU execution remains deferred
under the user's server-later instruction; no runtime success is inferred.
