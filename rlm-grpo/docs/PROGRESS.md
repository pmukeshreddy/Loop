# GRPO progress

## October 15 — repository GRPO implementation

Added `rlm_grpo`, `configs/grpo.toml`, and `grpo-*` Make targets. The new
phase initializes the native Prime-RL loop from a merged OPSD checkpoint,
executes root/child REPLs against one Docker checkout per rollout, grades a
captured patch in a separate container, and trains original model tokens with
+1/−1 verifier reward and leave-one-out advantages. See [the phase guide](../README.md).

Validation in this session: Python AST parsing, TOML parsing, pinned-source
inspection, and an independent static code review. Docker rollouts, adapter
merging, model inference, and GPU training use the pinned server environment.
The phase guide defines the dev solve-rate comparison and GRPO performance gate.

## October 15 — independent phase package

Moved GRPO into the top-level `rlm-grpo/` project and renamed its Python package
to `rlm_grpo`. GRPO owns its package metadata, server setup, Make commands,
configuration, policy assets, and documentation. Removed every runtime import
from OPSD, including its prompt configuration, decontamination helpers,
single-GPU smoke guard and trainer patch. The checkpoint export is the phase
handoff; the reserved DeepSWE snapshot is now an explicit external input.

The GRPO source overlay requires a pristine pinned Prime-RL checkout. The OPSD
Makefile and implementation-progress/API documents were restored to their
pre-GRPO contents; the OPSD agent guide points to the separate phase.

Validation: parsed all 12 GRPO Python modules and both TOML files, reviewed the
import graph for OPSD dependencies and stale paths, and checked shell syntax.
The policy and chat-template bytes retain their existing pinned checksums.

