# M8 independent review and closure

Read-only reviewer: `/root/m8_review`, gpt-6-astra, high reasoning. No file edits,
subagents or full-suite runs by the reviewer. First pass paused when the user
changed the scope; final pass reviewed the OPSD-only implementation.

Final findings, both P2:

1. Unscorable retention gold could make both policies score zero and pass the
   retention comparison. Added nine invalid-gold cases (numeric non-number,
   NaN/Inf/list; malformed/non-list/nonfinite list F1; nonscalar exact). All
   failed before the change. `RetentionItem.evaluable_gold` now rejects these
   before requests. Valid paired HTTP list-F1 responses remain exercised.
2. Decimal rates .8 minus .7 can be slightly above .1 in binary64 and fail an
   inclusive threshold. Added a boundary regression covering both criteria,
   and controls 1e-10 above the allowed drop. Failed before the change; now
   comparisons admit only four binary64 ULPs at 1 for subtraction roundoff.

Evidence: [10 red regressions](23-review-red.log), [36 green retention/exit
checks](24-review-green.log). Full post-fix suite: [final run](25-full-suite-final.log).
No substantive findings deferred. No re-review requested after the verified fix
pass. The reviewer confirmed no remaining M8 GRPO readiness/pass@k/entropy code.

Review limits: no real CUDA/model run or remote weight identity verification;
cancellation cleanup inspected, not experimentally exercised. User explicitly
requested server-ready code now and server execution later; these limits are
reported without converting fixture outcomes into model results. Documentation
was still being completed and was audited by the parent after review.
