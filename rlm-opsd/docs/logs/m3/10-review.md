# M3 read-only code review

Reviewer: `/root/m3_review`, a separate agent dispatched under the
requesting-code-review skill. Scope: SPEC §3, implementation plan, M3 prompt
package/config/assets/tests and harness integration. The project is untracked
in its parent repository, so review used the named final files instead of a Git
commit range. No reviewer edits or subagents were made.

Findings:

1. Important: recursive roots dropped the configured thinking flag. A focused
   reviewer rollout with thinking off showed the parent request carried
   `chat_template_kwargs.enable_thinking=False`, but its child sent only
   `max_tokens`. Fix: propagate PromptConfig to Episode/children and apply it to
   recursive-root requests; preserve child provider reasoning on later turns.
2. Important: the public dataclass constructor accepted arbitrary source text
   labelled `manual_v1`, bypassing source checks and allowing task metadata in the
   privileged addition. Fix: constructor now takes only a source directory and
   version and always performs registry/source/task-independence validation.
3. Minor in reviewer grading, treated as a correctness fix: a request-level
   `extra_body.chat_template` override was accepted while local prefix rendering
   used the pinned template. Fix: reject that override locally. Actual remote
   serving-template equality remains a later execution check.

All three received explicit failing regression tests before their fixes:
[08-review-regressions-red.log](08-review-regressions-red.log). Final results are
in [09-final-tests.log](09-final-tests.log). No reviewer finding was deferred.

The reviewer found the single-pass renderer, shared query, loaded manual,
prefix validation and noncanonical suffix-ID preservation sound.

Declined-to-judge items: then-unfinished M3 documentation; M4–M9; training-hook
integration; actual server-template parity; GPU/model behavior. The implementer
finished and audited M3 documentation. Later milestones and actual server/model
execution remain outside the user's M3-only scope and are explicitly unrun.
