# Repository GRPO after OPSD

GRPO is a separate phase in `rlm-grpo/`, installed as the `rlm_grpo` Python
package. The launch configuration is [`configs/grpo.toml`](configs/grpo.toml).
It owns its dependencies, commands, policy assets, Docker environment and trainer
integration. Its handoff from OPSD is an exported checkpoint. It does not import
the OPSD package or apply OPSD's trainer patch.

```text
rlm-opsd/   behavior distillation → exported checkpoint
rlm-grpo/   checkpoint + repository tasks → verifier-reward GRPO
```

## Setup

On the Linux/CUDA training machine, install the phase's independent environment:

```bash
cd rlm-grpo
make setup-server
```

This requires `git`, `uvx`, and an NVIDIA driver. The setup script creates
`.venv-server/` and a pristine `.deps/prime-rl` checkout at the commit pinned in
[`pyproject.toml`](pyproject.toml). It uses upstream's frozen runtime lock with
FlashAttention 2 and [`requirements-rlm.lock`](requirements-rlm.lock) for the
RLM additions. It does not read or modify `rlm-opsd/`. The setup command has
not been run in this implementation session.

The CLI is `python -m rlm_grpo` or the installed `rlm-grpo` command. Run the
Make commands from this directory. A custom `PRIME_SOURCE` must be pristine at
the pinned commit; a checkout with the OPSD distillation patch is rejected.

## Inputs

Run on the Linux/CUDA training machine with this phase's pinned server
environment and Docker. The Docker daemon must be local to the environment
workers. Each task image needs `git`, `python3` (3.10 or newer), its repository,
dependencies, and complete Git history through the specified base commit.
Images must not contain future solution commits, hidden grader files, or the
reference solution. Their `environment/Dockerfile` is the reproducible definition.

Set these paths in `[grpo]`; relative paths resolve from the TOML file:

```toml
[grpo]
opsd_checkpoint = "/checkpoints/opsd-merged"
manifest_path = "/datasets/synthetic-swe/manifest.jsonl"
heldout_dir = "/path/to/Loop/data/deep-swe/tasks"
```

The checkpoint must be a complete local HF BF16/FP16 export, including tokenizer
and chat template. The launcher initializes both training and inference from
this checkpoint and starts a fresh GRPO optimizer. It never substitutes the
original Qwen base. The operator is responsible for selecting the actual OPSD
export; the launcher validates its format, not its training history.
GRPO packages a copy of the same pinned Qwen chat template and RLM policy API
text in `rlm_grpo/assets/`, with checksums in `rlm_grpo/prompts.py`. Root and child
requests preserve the checkpoint's established thinking-enabled policy format.
No OPSD prompt configuration or teacher manual is loaded. The bundled Qwen
template's license is included as `rlm_grpo/assets/QWEN_LICENSE`.

If OPSD produced Prime-RL's portable adapter export, merge it first:

```bash
cd rlm-grpo
.venv-server/bin/python -m rlm_grpo merge-checkpoint \
  --base /models/pinned-qwen-base \
  --adapter /reports/opsd/weights/step_100 \
  --output /checkpoints/opsd-merged
```

This uses `safetensors` and PyTorch, processes one base-model shard at a time,
and writes provenance. It supports the existing dense-linear LoRA export with
no `modules_to_save`, DoRA, rank patterns, or MoE adapters. It merges into the
original dense base, as a portable QLoRA export; inference precision therefore
changes from the OPSD trainer's NF4 base to BF16/FP16. An export made elsewhere
is also accepted. The output directory must not already exist.

## Task pool

The GRPO manifest is a separate JSONL file, with one Harbor task bundle per row:

```json
{"task_id":"project-a-fix-001","split":"train","task_dir":"tasks/project-a-fix-001","repo_path":"/app"}
{"task_id":"project-b-fix-001","split":"dev","task_dir":"tasks/project-b-fix-001","repo_path":"/app"}
```

`task_dir` resolves from the manifest's directory. Each task contains
`task.toml`, `instruction.md`, `environment/Dockerfile`, and `tests/test.sh` plus
the task's grader/test assets. A reference solution may remain in `solution/`;
the loader and rollout runtime never read or copy it.

The task contract follows the checked-in DeepSWE Harbor bundles:

- `metadata.repository_url` and `metadata.base_commit_hash` identify the source.
- `environment.docker_image` selects the prebuilt image. If omitted, the runtime
  builds only the `environment/` directory. Build dependencies into the image.
- `environment.cpus`, `memory_mb`, `build_timeout_sec`, and `env` configure the
  container. `verifier.timeout_sec` and `verifier.env` configure grading.
- Agent and verifier run with Docker networking disabled. No host workspace,
  Docker socket, or model credentials are mounted into either container.
- The verifier is `bash /tests/test.sh`. It must apply
  `/logs/artifacts/model.patch` and produce `/logs/verifier/reward.json` with
  `{"reward": 1}` only when every required test passes, otherwise `0`.
  Existing DeepSWE graders do this, including applying their own `test.patch`.
  Missing/malformed rewards or a nonzero verifier exit are infrastructure errors.
- `repo_path` defaults to `/app`; a custom task's verifier must use the same path.
  Distinct verifier images and shared agent/verifier environments are rejected.

Only `train` and `dev` are accepted. The loader checks the whole manifest before
selecting a split, requires disjoint repositories, rejects duplicate IDs and
instructions, and excludes reserved DeepSWE IDs, repositories, and near-matching
instructions. The checked-in `data/deep-swe/tasks` snapshot is the exclusion
source and is never used as a training fallback. This is a conservative
repository/query screen, not a proof that every paraphrase is decontaminated.

The existing OPSD `data/manifest.jsonl` is a different, context-based format;
it is not silently relabeled as executable Harbor tasks. Supply the phase-3
repository-task release. No generated training tasks or model checkpoint are
included with this code change.

## Rollout and reward

Each of the eight configured group members starts an independent task container
before the model receives the instruction. The root sees the instruction and
repository-access metadata. Repository contents and commit history remain on
disk and are read selectively through Python REPL code.

`llm_query(prompt)` and `llm_query_batched(prompts)` run child RLMs through the
same pinned verifiers rollout loop. Each child has a persistent REPL for its
multi-turn assignment and shares the root's checkout. Calls use the same policy
client/model and sampling settings. A new subcall starts a new child; roots
retain results in their own REPL variables and pass earlier findings to later
assignments. Children can delegate within the shared call/depth limits. The root
coordinates edits and integration; the runtime does not merge competing edits
to the same file automatically.

The supported finishes are the OPSD `FINAL(...)` / `FINAL_VAR(name)` protocol
and the official worker's `answer['content']` / `answer['ready']` protocol.
Finishing on the last allowed turn executes normally. Missing variables and
Python exceptions return observations so the policy can recover.

When the root submits, all worker process groups stop before patch capture.
A private Git index collects committed, staged, unstaged, deleted, and new
non-ignored files against `base_commit`. A fresh verifier container receives
only this patch and the task's grading assets.

Reward is **+1 for all required tests passing, −1 for a submitted failing or
invalid solution**. No partial credit or behavior bonus is added. Unsubmitted,
truncated, timed-out, and infrastructure-failed rollouts are ineligible for
the update and excluded from the advantage baseline. A failed child assignment
returns an error to the parent, which may recover; incomplete child token
branches are excluded. Root instructions and code that led to recovery remain
part of a successfully submitted root trajectory.

Artifacts live under `reports/grpo-27b/trajectories/{train,dev}/<episode>/`:
`model.patch`, `result.json`, and `verifier/` logs/reward/test reports. Prime-RL
retains the model trajectories, checkpoints, optimizer state, and rollout
metrics through its native lifecycle.

## Objective and launch

The native custom-advantage hook computes leave-one-out advantages among eligible
members of the same task group, without reward-standard-deviation division.
Groups with fewer than two eligible members, all passes, or all failures have
zero advantage and are filtered. Prime-RL retries empty filtered batches and
stops after its pinned three-attempt limit; it does not silently train on an
empty signal. Inspect task difficulty and `eligible` metrics if this occurs.

The custom loss is the clipped PPO/GRPO surrogate with `clip_low=0.2`,
`clip_high=0.28`, no reference KL, and no entropy bonus. Root and completed child
assistant tokens retain their original token IDs/logprobs; prompt and observation
tokens are masked. Native multi-prefix interleaving keeps agent branches distinct.

A narrow source overlay replaces the pinned trainer's actual-token denominator
with **global active sequence count × maximum context length**. A sequence is
a native root/child token branch; padding sequences do not count. The scale
compensates for FSDP gradient averaging. This avoids response-length-dependent
normalization. The overlay is generated into the run directory from the verified
Prime-RL pin into this phase's run directory. It does not modify the source
checkout or installed packages.
The current path supports data parallelism with `cp=ep=1`.

```bash
cd rlm-grpo
# Pull/build once before training; no agents or tests execute here.
make grpo-prepare-images PYTHON=.venv-server/bin/python \
  GRPO_MANIFEST=/datasets/synthetic-swe/manifest.jsonl \
  GRPO_HELDOUT=/path/to/Loop/data/deep-swe/tasks

# Optional configuration/source validation; no Docker or model execution.
make grpo-check PYTHON=.venv-server/bin/python

# Native async inference + orchestrator + distributed trainer.
make grpo-train PYTHON=.venv-server/bin/python
```

`make grpo-smoke` uses the same path with `--max-steps 1`; running it executes
real rollouts, graders, and a GPU update. It was not run during implementation.
Use a different `output_dir` for a smoke experiment. GPU counts, batch sizes,
context length, and rollout budgets in the supplied config are editable starting
settings, not hardware performance claims. Docker capacity must cover the
configured in-flight rollout count and task resource limits.

Dev evaluation uses the same task/verifier/runtime budgets at step zero (the
OPSD baseline) and every 25 updates. `solved` is the binary success metric;
reward averages use the +1/−1 scale. Public DeepSWE remains a final reporting
benchmark through the separate evaluation workflow, never the tuning pool.

Implementation verification: Python syntax and TOML parsing plus source review
only. Tests, Docker execution, checkpoint merging, native configuration imports,
GPU training, and solve-rate comparisons were **not run** at the user's request.
