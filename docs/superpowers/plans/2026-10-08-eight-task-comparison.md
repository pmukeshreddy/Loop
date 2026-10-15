# Eight-task comparison implementation plan

> Execute inline using executing-plans and verification-before-completion. The project root has no Git repository; work in place and retain results.

**Goal:** Run the existing eight DeepSWE problems with native Codex and official RLM, then report all sixteen outcomes.

**Spec:** The user's request and the benchmark gate in `01-prove-harness.md`. The user selected 10 minutes per attempt.

**Design:** Use the existing seed-0 slice, `gpt-6.1-sol`, medium reasoning, and 600 seconds for each attempt. Both agents edit `/app` in separate containers based on the same prepared task image. RLM uses its unchanged local environment inside Docker, with repository text in `context`, normal filesystem/shell access, and its built-in subcalls. Native Codex uses its normal CLI loop. Score captured working-tree patches in pristine containers with the supplied hidden verifiers.

**Constraints:** No solutions or hidden tests in agent containers. No task selection based on new outcomes, no model-assisted repair, and no retries of failed model attempts. An internal Docker network permits only an OpenAI HTTPS proxy; grading has no network. The local Docker VM has 4 GB RAM, so execute attempts sequentially with 2 CPUs and a 3 GB container limit; record this reduction from the task's 8 GB recommendation. Timeouts retain the patch present at the deadline for grading and remain explicitly marked as timeouts. This is a local 10-minute pilot, not a leaderboard replication.

## Tasks

- [x] 1. Add a small benchmark runner (`step1/benchmark.py`), container worker (`step1/benchmark_worker.py`), and API-only CONNECT proxy (`step1/api_proxy.py`). Extract reusable native Codex command construction in `step1/codex.py`. Keep setup and grading outside the timed solve period. Save manifest, source/version hashes, patches, event/trajectory logs, statuses, rewards, and verifier output. Refresh project OAuth before each attempt.
- [x] 2. Add focused behavioral tests in `step1/tests/test_benchmark.py`: capture new/committed/uncommitted changes from a real Git fixture; recognize verifier infrastructure errors separately from reward zero; exclude binary files from RLM's context while retaining tracked source; reject proxy destinations other than OpenAI; ensure recursive usage is not silently presented as root-only totals. Run the complete suite and lint.
- [x] 3. Prepare one common Python/Codex runtime, add it to the existing task images, and run a real Docker plumbing check with an empty patch and the supplied verifier. Verify both agents can reach OpenAI through the restricted network and cannot reach unrelated sites. Have a fresh reviewer check the runner before the sixteen attempts.

## Evaluation procedure

1. Freeze the manifest and run every task once per arm. Alternate which arm goes first. Run unmodified verifiers in fresh, offline task containers. Record setup/grading failures separately; only repair infrastructure with an explicit record, never model patches.
2. Produce a per-task comparison and aggregate solve counts, timeouts, partial test counts, wall time, and usage. Explain the small sample and resource/time limits. Update `01-prove-harness.md` with the report link.

## Review focus

- Hidden-test leakage or old patched checkouts used as input.
- Deadlines leaving agent processes alive during patch collection.
- Missing verifier reports incorrectly scored as agent failures.
- Lost new files or committed edits in patch collection.
- Recursive child token counts omitted or counted twice.

## Progress

- Docker is available; all eight task images are cached. The fixed slice is `step1/results/slice.json`. The supported project OAuth and Responses adapter are already live-tested.
- The user confirmed 600 seconds per attempt. No root Git repository exists, so Git-based plan scripts/commits do not apply.

- Final review fixed three findings: a private Git index preserves patches after interrupted Git operations; patch capture precedes optional worker telemetry, whose writes are atomic; per-request usage logging in the Responses adapter includes depth-capped recursive calls. All three regressions were observed failing before fixes. Full suite: 29 passed; Ruff passes. No RLM core/environment changes.
- Runtime verification: both native Codex and official RLM completed a live 42-result fixture inside Docker; proxy and direct external requests to unrelated destinations were blocked. A real container deadline test preserved its patch despite a stale Git lock. Every prepared task image has the correct base commit, a clean tree, and no /tests or /solution mount. The empty Bandit patch scored reward 0, with 275/275 pass-to-pass and 0/88 fail-to-pass tests.
- Review's unassessed Docker/runtime cases were checked above. Per-task grading under the local 3 GB limit remains observable in the scored run; any failure is recorded separately.

- Operational auth fix: credentials now refresh with enough validity for the full requested attempt budget. The already-running frozen controller is accompanied by the same project-owned OAuth helper refreshing with a 15-minute margin; solver images/model prompts are unchanged. Regression test passed; full suite now 30 passed.
- First scoring limitation: SCC Codex completed in 489.121 seconds. Its grader passed all 31 fail-to-pass tests but omitted one pass-to-pass test after an OOM event (285/286). This is recorded as infrastructure-limited, not a solved or cleanly failed problem. The host has 8 GB total RAM and Docker has 4 GB, so the task's recommended 8 GB cannot be provided comfortably on this machine. Investigate ordinary Go memory settings for verifier-only reruns, preserving all original patches and results.
