# Refine DeepSWE

Train a 27B model to solve software-engineering tasks using the official Recursive Language Model (RLM) library.

## Phase 1 harness

First verify the OpenAI connection with a small behavioral comparison:

- **Codex:** the native Codex CLI works on a tiny Python repository.
- **RLM:** the same OpenAI model supplies text completions to the official RLM loop. The library executes REPL blocks, keeps state, and makes recursive calls.
- Both patches go through the same executable verifier in fresh checkouts.

The Cursor integration has been removed. The old benchmark artifacts remain under `step1/results/` for historical reference and are not reused by the new runner.

See [phase 1](01-prove-harness.md) for setup, authentication, checks, and the later benchmark gate. See the [implementation plan](docs/superpowers/plans/2026-10-08-phase1-openai.md) for progress.

## Pipeline

OPSD and GRPO are separate projects: `rlm-opsd/` trains RLM behavior;
`rlm-grpo/` trains repository correctness from the exported OPSD checkpoint.
See [GRPO setup and launch instructions](rlm-grpo/README.md) for the checkpoint
handoff, Docker task manifests, shared-checkout child rollouts, and verifier rewards.
Docker rollouts and GPU training use the Linux/CUDA server environment.

| Step | Purpose |
|---|---|
| [1 — Prove the harness](01-prove-harness.md) | Verify integration, then compare solve rates on held-out DeepSWE tasks. |
| [2 — OPSD](02-opsd.md) | Teach the 27B to produce RLM actions. |
| [3 — Synthetic tasks](03-synthetic-deepswe.md) | Build executable training tasks, separate from the evaluation set. |
| [4 — GRPO](04-grpo.md) | Improve verifier success using those actions. |

The official RLM REPL and core execution loop remain in use. We add one Responses API client through the library's normal backend interface; we do not implement a second agent loop.

Behavioral checks prove integration correctness, not a solve-rate improvement.
The public 113 tasks remain evaluation-only. The phase-4 guide documents the
GRPO implementation, server requirements, and evaluation workflow.

## Publish

The publish script copies the files listed in `scripts/push-manifest.json` into
a fresh checkout of `pmukeshreddy/Loop`, removes the former nested GRPO package,
and pushes a commit to `main`. It checks the manifest's base commit before
applying changes and preserves the repository's history.

```bash
bash scripts/push.sh --dry-run
bash scripts/push.sh
```

The dry run prints the staged diff summary and a command to inspect the full
diff. The script requires Git, Python 3.8 or newer, and GitHub push access.
`--remote URL` selects another repository with the same base commit.
