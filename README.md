# Refine DeepSWE

Train a 27B model to solve software-engineering tasks using the official Recursive Language Model (RLM) library.

## Current focus: phase 1

First verify the OpenAI connection with a small behavioral comparison:

- **Codex:** the native Codex CLI works on a tiny Python repository.
- **RLM:** the same OpenAI model supplies text completions to the official RLM loop. The library executes REPL blocks, keeps state, and makes recursive calls.
- Both patches go through the same executable verifier in fresh checkouts.

The Cursor integration has been removed. The old benchmark artifacts remain under `step1/results/` for historical reference and are not reused by the new runner.

See [phase 1](01-prove-harness.md) for setup, authentication, checks, and the later benchmark gate. See the [implementation plan](docs/superpowers/plans/2026-10-08-phase1-openai.md) for progress.

## Pipeline

| Step | Purpose |
|---|---|
| [1 — Prove the harness](01-prove-harness.md) | Verify integration, then compare solve rates on held-out DeepSWE tasks. |
| [2 — OPSD](02-opsd.md) | Teach the 27B to produce RLM actions. |
| [3 — Synthetic tasks](03-synthetic-deepswe.md) | Build executable training tasks, separate from the evaluation set. |
| [4 — GRPO](04-grpo.md) | Improve verifier success using those actions. |

The official RLM REPL and core execution loop remain in use. We add one Responses API client through the library's normal backend interface; we do not implement a second agent loop.

Behavioral checks prove integration correctness, not a solve-rate improvement. Do not start phase 2 until a controlled DeepSWE comparison shows RLM solving more tasks. The public 113 tasks remain evaluation-only.
