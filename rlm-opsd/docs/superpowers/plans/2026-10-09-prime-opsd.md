# Prime-rl OPSD integration implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Run repeated OPSD updates through prime-rl's native async rollout, FSDP2 trainer, checkpoint, and vLLM adapter synchronization loop.

**Architecture:** Carry original per-turn student IDs and aligned teacher IDs through the native transport. Use one unpadded turn per microbatch, with native distribution and zero-loss dummy batches. Install a chunked JSD output head before FSDP wrapping; call the wrapped model for a frozen teacher pass before the student pass, then let the existing trainer perform backward and optimizer/scheduler updates. Deliver upstream edits as a checked patch against the exact pin and launch every process with that source overlay.

**Tech stack:** prime-rl 09e11c7527a242b9f150c7c4c71b1b96da66cb75, PyTorch, custom MultiLoRA, verifiers, vLLM.

**Spec:** User request plus `docs/SPEC.md` sections 3 and 6; `AGENTS.md`.

## Global constraints

- Local verification covers CPU FSDP. GPU FSDP/vLLM acceptance requires server execution and its logs.
- Root assistant targets only; no SFT, reward objective, remote teacher scoring, or held-out training data.
- Preserve token IDs, separate prefix positions, frozen base weights, adapter state/RNG, and checkpoint recomputation.
- Keep upstream optimization_dtype and reduce_dtype unchanged.
- Start with single-run dense HF Qwen3.5, FSDP data sharding, no context/expert parallelism or compilation. Reject unsupported combinations.
- Execute in the current workspace, preserving existing dependency installations and unrelated files. The user has specified the integration and authorized implementation; no additional design approval is needed.

## Review focus

- Unequal target counts across ranks: globally normalize with FSDP's gradient averaging accounted for.
- Empty local masks: execute the same forwards/backward collectives and contribute zero gradients.
- Teacher prefix longer than student: reject truncation and preserve exact suffix/causal alignment through serialization.
- FSDP parameter lifetime: project inside the wrapped head; teacher first, restore state before student forward/backward.
- Fresh deployment: patch, configuration packages, subprocess imports, environment factory, and launcher must resolve the same source.

### Task 1: Native rollout and transport integration

Files: `training/prime_data.py`, `training/prime_env.py`, pinned transport/batch/orchestrator/config sources, `tests/test_prime_opsd_data.py`.

- [x] Write and run failing tests for multi-turn conversion, serialization, no packing/truncation, dummy distribution, and unchanged ordinary batches.
- [x] Attach exact prefixes through environment output; convert original token records to TrainingSample and transport teacher IDs/positions.
- [x] Run CPU data tests; record results.

### Task 2: FSDP-compatible loss hook

Files: `training/prime_step.py`, `training/teacher.py`, pinned trainer/model/config sources, `tests/test_prime_opsd_step.py`.

- [x] Write and run failing tests for native wrapped forwards, dense-reference loss/gradients, repeated optimizer updates, activation checkpointing, frozen teacher invariance, empty masks, and configuration rejection.
- [x] Install JSD head before FSDP; replace normal loss under OPSD; preserve native optimizer/broadcast/checkpoint loop and global normalization.
- [x] Run CPU tensor/integration tests; record GPU FSDP server acceptance requirements.

### Task 3: Reproducible patch and training command

Files: `patches/prime-rl-opsd.patch`, `training/prime_patch.py`, `training/prime_launch.py`, `configs/opsd_train.toml`, `Makefile`, tests and docs.

- [x] Verify exact upstream source identity; create an idempotent patch installer without modifying site-packages.
- [x] Add `make opsd-train` and CPU-only check, pinned model snapshot resolution, real teacher-gate preflight, native RL config, and environment loader.
- [x] Test patch reconstruction/config/launcher, run project suite and review integration; update VERIFIED_APIS, PROGRESS, usage and log evidence.

## Execution record

Initial source review: native trainer owns a repeated loop, weight broadcast, optimizer and checkpointing. Existing smoke helper rejects FSDP and invokes the backbone directly. Existing native packing can truncate sequences and averages locally normalized gradients; the OPSD branch must avoid both behaviors.

Execution complete. Independent review findings (snapshot renderer lookup,
token fallback, CPU offload rejection, and step-level JSD metric aggregation)
were addressed before final testing. `make test`: **604 passed**, including
real one-/two-rank CPU FSDP and repeated-update dense-reference gradient parity.
See [execution record and logs](../../PROGRESS.md#prime-rl-opsd-multi-step-integration).
Preflight correctly stops at the absent teacher gate report. The evidence covers
CPU tests and preflight; GPU acceptance requires the configured server.
