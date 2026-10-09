# Phase 1 — Connect OpenAI, then prove the harness

The immediate deliverable is a small, understandable behavioral check of **native Codex versus the official RLM harness**, using the same explicit OpenAI model. This supersedes the earlier Cursor design.

## Architecture

`step1/codex.py` runs the native `codex exec` agent in a temporary repository. `step1/run_eval.py` calls official `RLM.completion(context, root_prompt=instruction)` through the `openai_responses` backend. `step1/rlm_worker.py` is only a process boundary so the runner can stop a stuck REPL. It contains no replacement REPL or agent loop.

The Responses client sends conversation history directly to `https://api.openai.com/v1/responses`, returns all completed message text, and tracks usage. It preserves each assistant message's phase when replaying history and converts system messages to developer messages for the documented ChatGPT-plan API requirements. Both root and recursive calls use the selected model. The official RLM library handles execution, state, feedback, and recursion.

Each arm solves the same tiny `total.py` task. Both submissions are applied to fresh repositories and checked with the same Python assertions. RLM additionally must show REPL execution, a successful plain call, a successful recursive call, and an executed `answer` submission. Fallback prose is not a submission. Both harness processes have an external wall-clock deadline.

## Setup

Python 3.11+ and Codex CLI are required. The CLI flags are checked against locally installed Codex 0.162.0.

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

The editable dependency points at [the official RLM source](https://github.com/alexzhang13/rlm) at commit `72d6940142ddfb84ee6be573dc999a37e633e671`, plus our Responses backend and registration. The core loop and environments are unchanged.

## Authentication

Choose explicitly; the runner never switches authentication or billing modes automatically.

**ChatGPT plan (default):** use the official project-owned OAuth registration:

```sh
.venv/bin/python -m step1.auth login
.venv/bin/python -m step1.auth models
```

Open the printed OpenAI URL on this computer, sign in, and authorize `Refine DeepSWE`. The callback must finish on this computer. A successful login writes owner-only credentials under ignored `.phase1-auth/`; the runner refreshes expired tokens before starting. A properly authorized `ACCESS_TOKEN` in the environment is also supported. Existing Codex credentials are not extracted or reused as a general API token.

ChatGPT-plan requests use eligible plan allowance and remain subject to account/workspace limits. OAuth itself does not mean unlimited free inference. Availability must be confirmed by a completed request.

**API billing:** set `OPENAI_API_KEY` in your terminal and pass `--auth api-key`. This is billed through the OpenAI Platform account. Do not put the key in a prompt, command argument, or committed file.

Both arms use the chosen credential through the public Responses endpoint. The Codex baseline receives it through its documented provider configuration.

References: [ChatGPT-plan inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [registration](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), [requirements](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations), [Codex provider configuration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server).

## Checks

Offline behavioral tests replace HTTP/process transport where necessary while exercising the real SDK, official REPL, recursion, and patch verification:

```sh
.venv/bin/python -m pytest -q
```

The official RLM uses a localhost socket, which must be permitted by the execution environment.

Run one live comparison after signing in, substituting a model ID from the account's model catalog:

```sh
.venv/bin/python -m step1.run_eval --model MODEL_ID --auth chatgpt
```

Use `--arm rlm` or `--arm codex` to diagnose one side. `--timeout 120` is the default per-arm limit. Each invocation creates a new directory under `step1/results/openai-behavior/` containing patches, RLM trajectories, and `results.json`. Exit code 0 means every requested arm passed its behavioral checks. A failed request, timeout, or failed verifier returns 1.

The live fixture is a wiring check. The deterministic suite also verifies persistent state, actual error feedback, incomplete-response rejection, model consistency, and timeout cleanup. Neither is a DeepSWE score.

## Verified result — October 8, 2026

All 21 project tests pass. The final live check used `gpt-6.1-sol`, ChatGPT-plan OAuth, medium reasoning effort, and `--timeout 240` for both arms:

| Harness | Patch verifier | Wall time |
|---|---|---|
| Native Codex | PASS | 23.662 seconds |
| Official RLM | PASS | 98.492 seconds |

RLM also completed REPL execution, a plain model call, a recursive RLM call, and an executed answer submission. [Raw results](step1/results/openai-behavior/run-uqbic2ne/results.json) and [implementation notes](docs/superpowers/plans/2026-10-08-phase1-openai.md) retain the evidence and earlier diagnostic failures. These are one successful wiring check, not a benchmark comparison. RLM's reported top-level token usage excludes recursive child usage, which is in the trajectory.

## Later benchmark gate

The eight-task pilot uses `step1/benchmark.py` with the existing seed-0 slice. Prepare the native Codex/Python runtime, then run one attempt per harness per task:

```sh
.venv/bin/python -m step1.benchmark --prepare
.venv/bin/python -m step1.benchmark --model gpt-6.1-sol --timeout 600
```

Each arm receives a clean container from the same task image, medium reasoning, two CPUs, 3 GB memory, and 600 seconds. The local Docker VM has only 4 GB, below DeepSWE's recommended 8 GB per task. Solves are sequential and have access only to OpenAI's public API; the hidden verifiers run offline in separate pristine containers. Native Codex's execution sandbox is the Docker container. Official RLM runs its unchanged local REPL inside its container and edits the same `/app` repository.

The runner collects committed and uncommitted changes when an attempt completes or reaches its deadline. It records timeouts, resource limits, API failures, and verifier infrastructure failures separately. This working-tree collection and short resource budget make the run a local pilot, not a leaderboard replication. RLM usage is logged per completed request, including recursive depth-cap calls; interrupted requests can leave usage incomplete. The project OAuth refresh margin covers a full attempt.

The [pilot plan](docs/superpowers/plans/2026-10-08-eight-task-comparison.md) tracks verification and progress. The current run is under `step1/results/openai-eight/run-20261008-gpt6.1-sol-600s/`.

Keep reference solutions and hidden tests out of model context. Record solve rate, wall time, usage, recursive behavior, and verifier failure details. Never mix old Cursor results with OpenAI results.

Proceed to phase 2 only if RLM solves more tasks than native Codex. Otherwise stop. The Datacurve 113 stay evaluation-only.
