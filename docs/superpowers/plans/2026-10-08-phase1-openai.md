# Phase 1 OpenAI integration implementation plan

> Execute inline with the executing-plans and test-driven-development skills. Track progress here; the project root is not a Git repository.

**Goal:** Replace the Cursor integration with a small, reviewable Codex-versus-RLM behavioral comparison using the same OpenAI model.

**Design:** Codex CLI owns the baseline agent loop. The official RLM library owns the other loop and receives plain text from a streaming OpenAI Responses client. Both work on the same tiny Python task in independent temporary checkouts. This establishes integration correctness before another DeepSWE benchmark run.

**Authentication:** Explicit `--auth chatgpt` uses this project's own OAuth registration and documented ChatGPT-plan Responses access. Explicit `--auth api-key` uses `OPENAI_API_KEY`. No credential extraction from Codex, private endpoints, automatic billing fallback, or nested Codex agent inside RLM. Model selection is an explicit `--model` argument.

**Acceptance:** RLM reads context, executes code, preserves state, observes an execution error, uses plain and recursive subcalls, and submits through `answer`. Both arms produce patches that pass the same small verifier. Offline tests substitute only the HTTP/process transport; live checks are clearly distinguished. Interrupted/failed responses cannot become successful completions.

## Tasks

- [x] 1. Add failing behavioral tests for a streaming Responses backend, including request roles, incomplete streams, state/feedback, both subcall types, and final submission. Implement the small backend in `third_party/rlm/rlm/clients/openai_responses.py`; register it without changing the RLM core.
- [x] 2. Replace `step1/run_eval.py` with a small behavioral comparison and `step1/codex.py` with the native CLI invocation. Verify actual patch application, identical fixtures, failure reporting, explicit model/auth, and process timeouts. Remove the Cursor adapter and obsolete Cursor tests. Preserve historical results and benchmark data.
- [x] 3. Add a documented OAuth sign-in helper and API-key option in `step1/auth.py`. Test callback validation and grant handling. Keep credentials outside result logs, owner-readable only, and support token refresh. Update phase documents to supersede the Cursor decision.
- [x] 4. Run the complete project test suite and lint changed Python. Run a small live check when project credentials are available. Record the exact outcome; do not equate behavioral success with improved DeepSWE solve rate.

## Review focus

- OAuth system-message restrictions, interrupted streams, and expired credentials.
- Recursive calls using the same model and transport as the root.
- A patch-shaped final text without an executed `answer` submission.
- Native CLI failure or timeout leaving partial edits behind.
- Claims about live success or benchmark improvement unsupported by actual runs.

## Progress

- Initial inspection: Codex 0.162.0 installed; native CLI is logged in with ChatGPT. No `OPENAI_API_KEY` in the current environment. Official docs describe a separate supported OAuth registration for this project's direct Responses calls.
- Existing flow: Cursor adapter plus a large evaluation runner; no root Git repository. Work in place, preserve existing benchmark artifacts, and replace the authorized integration code.

- Review fixes: external process deadline for RLM, fixed model for subcalls, async usage propagation, and persisted OAuth registration across failed exchanges. Each has a regression test.
- Validation: `.venv/bin/python -m pytest -q` passed all 21 tests. Changed Python passes Ruff lint and formatting. Official RLM core loop and environments have no diff; `git diff --check` passes in the RLM checkout.
- Authentication: project-owned OAuth completed and both live arms successfully used the public Responses endpoint with the ChatGPT-plan grant.
- Live-response fixes: consume streamed text when the terminal response has an empty output array; return all message text to RLM and replay the original assistant message boundaries and phases. Regression tests cover interrupted streams, multiple message phases, and empty final messages.
- Final live command: `.venv/bin/python -m step1.run_eval --model gpt-6.1-sol --auth chatgpt --timeout 240`. Both arms passed: Codex in 23.662 seconds; RLM in 98.492 seconds. RLM executed the REPL, completed plain and recursive calls, submitted through `answer`, and passed the same fresh-checkout verifier as Codex. [Results](../../../step1/results/openai-behavior/run-uqbic2ne/results.json), [RLM patch](../../../step1/results/openai-behavior/run-uqbic2ne/rlm/model.patch), [Codex patch](../../../step1/results/openai-behavior/run-uqbic2ne/codex/model.patch).
- Earlier diagnostic runs remain unchanged under `step1/results/openai-behavior/`; they include response-parsing failures and 120-second timeouts. The final result establishes a successful behavioral run, not a reliability rate or a performance advantage. RLM's top-level usage excludes recursive children; those calls are recorded in its trajectory.
- Integration work is complete. The controlled eight-task DeepSWE comparison remains the next phase-1 gate; phase 2 has not started.
