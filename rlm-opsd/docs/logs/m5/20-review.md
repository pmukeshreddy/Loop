# M5 review and closure

Read-only reviewer: `/root/m5_review`, invoked through the requesting-code-review
workflow. No reviewer edits, duplicated full suite, commit or push.

Initial findings and test-first fixes:

1. A worker infrastructure failure could satisfy a permissive syntax criterion.
   The gate now rejects structured harness infrastructure failures.
2. Provider authentication exception text could reach the REPL/model and logs.
   The client replaces provider text with exception type before that boundary.
   Root and frozen-client regressions use a sentinel provider response.
3. Outer construction/analysis/client-cleanup failures could prevent final
   error artifacts or cleanup of the other client. The runner handles these
   paths, closes clients independently and preserves partial traces.

[08-review-red.log](08-review-red.log): six failures before fixes.
[09-review-green.log](09-review-green.log): all 34 then-current M5 tests passed.

Full regression exposed an existing sandbox cleanup race. The reviewer inspected
the once-only process-group signal and explicit wait before resource-limit EOF,
including first-permission-error propagation and unchanged real-worker checks.
[14 investigation](14-cleanup-investigation.log), [15 red](15-cleanup-red.log),
[16 green](16-cleanup-green.log) preserve that evidence.

Follow-up found a recursion edge: a child worker error could be swallowed into
the root's successful final answer. The reviewer executed the real harness with
a local HTTP fixture and observed status passed, completed=12, errors=[], and
12 child worker-error traces. This was a synthetic reproduction, not model data.

[18-recursion-red.log](18-recursion-red.log) independently reproduced false
passes for child setup, execution and cleanup; the budget-only control passed.
The fix shares structured infrastructure errors through all descendant Episodes,
invalidates the gate, and retains links to failed child traces. Budget hits during
assistant execution remain measured behavior. Tests cover all four paths.

Final read-only review: no further substantive findings. Review closure did not
claim a test result; the implementer verifies [19-recursion-green.log](19-recursion-green.log)
and the final full suite separately. Runtime/GPU claims remain not run.
