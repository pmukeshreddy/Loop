# M6 independent review and closure

Read-only reviewer: `/root/m6_review`. Reviewed shared sample alignment, native
sampled loss, adapter bypass/restoration, backend source calls, smoke runner and
tests. No reviewer edits were made.

Initial findings:

1. P1: generation left top-p/top-k and penalties to server defaults while local
   scoring used unrestricted softmax. Exact pinned Qwen27 generation config has
   top-k 20/top-p 0.95. Nonunit temperature also requires processed logprobs.
2. P2: aligned token arrays with Verifiers `is_truncated`/`overlong_prompt` flags
   could pass; this admitted clipped histories. Generation budget termination
   with complete records must remain valid.

Both received red regressions in [15-review-red.log](15-review-red.log) before
the fixes. [16-review-green.log](16-review-green.log) passes the new regressions
and prior tests. Root generation now sends explicit neutral filters/penalties;
config requires an operator declaration of processed logprobs. Alignment rejects
token-record clipping while accepting a generation length stop.

Additional parent findings received their own red tests: HF snapshot symlinks
must be allowed to point to cache blobs while index traversal is rejected;
LoRA must explicitly select ordinary matmul for the portable smoke; gate trace
phase/task metadata and request roles must agree with the current evidence.
See [14 runtime red](14-runtime-edges-red.log),
[19 evidence red](19-evidence-red-corrected.log), and
[20 final M6 green](20-m6-green.log).

Reviewer follow-up confirmed both initial findings resolved, checked Verifiers
request forwarding, and independently reported 15 focused tests passing. No
new substantive issue was found. Parent's retained, directly executed complete
evidence is [21-full-suite.log](21-full-suite.log): 427 pytest tests plus 3 M0
checks passed.

Explicit review limits retained in the docs: `logprobs_mode` is operator-declared,
not remotely verified; the tiny random Qwen test covers full attention plus the
actual pinned head/LoRA/loss, not pretrained loading, hybrid attention, CUDA,
FSDP or compilation. CPU fixture success is not either real pretrained smoke.
