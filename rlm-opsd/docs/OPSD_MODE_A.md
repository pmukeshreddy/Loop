# M6: shared local teacher hook and optional Mode A smoke

Mode B remains primary. M6 implements the shared frozen-base teacher hook and
an **optional, synchronous, one-task / one-update Mode A correctness smoke**.
JSD, its memory-bounded projection and the optional token gate belong to M7.
There is no teacher scoring endpoint or scoring API request.

M7 now implements that primary path; see [OPSD_MODE_B.md](OPSD_MODE_B.md).
The commands below continue to select optional Mode A explicitly.

The runner uses pinned prime-rl model, MultiLoRA, output-head and sampled-loss
code. It does not invoke the upstream asynchronous training loop or add teacher
prefix fields to its transport schema. It supports one dense adapter, one CUDA
GPU/process, eager execution and unpadded per-turn sequences. Distributed,
compiled, MoE, packed and resumed training are outside this smoke's scope.

## Server preparation and order

Run from `rlm-opsd/` in the pinned Linux/CUDA environment installed by
[setup_m0_server.sh](../scripts/setup_m0_server.sh). Use `PYTHON` to select that
environment. The ordinary-matmul LoRA path avoids the grouped kernel dependency
for A100/H100 portability; GPU compatibility and memory fit are still **not
run**. The 27B eager/full-logit path requires substantial device memory. No
multi-GPU or quantized fallback is implemented.

1. Complete the M2 decontaminated pool and set the user-owned detector and gate
   thresholds. Run the [teacher gate](TEACHER_GATE.md) for each model at its exact
   pin using `configs/gate_small.yaml`, then `configs/gate.yaml` as appropriate.
   A missing, failed, stale, partial or fixture gate cannot authorize a smoke.
2. Cache the full model snapshots at the exact revisions in the smoke configs.
   Weight acquisition is an operator step; this runner uses
   `snapshot_download(..., local_files_only=True)` and never downloads weights.
   Prepare the small tokenizer with the existing command below. Its template
   differs from the 27B template and has a separate config.
3. Serve the initial frozen model for root generation and frozen leaf calls,
   using the declared revision, pinned chat template and thinking mode. New
   LoRA B matrices must be zero, so the initial student equals the served base.
   This runner stops after its first update; it does not serve the resulting
   adapter, broadcast weights, resume, or collect post-update rollouts.
4. The root server must return original prompt/completion token IDs and sampled
   logprobs. Use **processed_logprobs**, as selected by pinned prime-rl inference.
   Plain vLLM defaults to raw logprobs; configure its model's `logprobs_mode`
   accordingly. The smoke TOML setting is an **operator declaration**, not
   remote verification or a request that reconfigures the server. Do not use
   custom logits processors, constrained decoding or hidden policy alterations.

```bash
.venv-server/bin/python -m rlm_opsd.prompts prepare --config configs/prompts_small.yaml

make teacher-gate PYTHON=.venv-server/bin/python \
  GATE_CONFIG=configs/gate_small.yaml GATE_OUTPUT=reports/teacher-gate-small-manual_v1
make opsd-a-check PYTHON=.venv-server/bin/python OPSD_CONFIG=configs/opsd_mode_a_small.toml
make opsd-a PYTHON=.venv-server/bin/python \
  OPSD_CONFIG=configs/opsd_mode_a_small.toml OPSD_OUTPUT=reports/opsd-a-small

make teacher-gate PYTHON=.venv-server/bin/python \
  GATE_CONFIG=configs/gate.yaml GATE_OUTPUT=reports/teacher-gate-manual_v1
make opsd-a-check PYTHON=.venv-server/bin/python
make opsd-a PYTHON=.venv-server/bin/python
```

Update endpoint URLs/served aliases before each gate, keeping each gate config
and its evidence intact. Gate provenance must match the current config, data,
prompts and detector settings. The 27B smoke additionally requires the completed
small pretrained smoke and the matching saved checkpoint hash. CPU tests do
not satisfy that prerequisite.

## Scoring contract

Generation explicitly sets `top_p=1`, `top_k=-1`, `min_p=0`, repetition penalty
1 and frequency/presence penalties 0. Student and teacher logprobs are computed
from unrestricted full softmax at the configured positive temperature. This
overrides the pinned model's generation filters and makes the inference
denominator use the same policy convention; endpoint bytes and conventions
remain operator-declared. Responses must match the configured served alias.

For each root turn, the trainer reads the original Verifiers token record.
Only that turn's selected completion tokens are targets; earlier completions
and observations are prompt history. It creates the teacher sequence by exact
prefix-ID replacement, checks the suffix, and maps causal positions separately
for the two prefix lengths. Missing IDs/logprobs, changed prefixes, Verifiers
clipping flags and overlength aligned sequences fail. Reaching the generation
token budget with complete records is allowed. No text is re-tokenized to
repair a record, and task answers never enter samples or the loss.

Student forward runs first. A serialized context then bypasses each dense
MultiLoRA adapter's computation, runs the frozen base in evaluation/no-grad
mode, and restores forward methods, modes, RNG, global token counts and scales
in place before backward. The lock covers the full student/teacher/backward
step. Base parameters, embeddings and the output head must remain frozen.

Mode A calls prime-rl's native `default_loss_fn` with `adv_tau=0`,
`teacher_tau>0`, `kl_tau=0`, and unclipped DPPO bounds of 1. It averages the
summed sampled-token objective over selected root tokens, detaches teacher and
inference logprobs, clips finite gradients and updates only LoRA A/B parameters.
An empty mask does not update; the smoke rejects a rollout with no targets.
See [VERIFIED_APIS](VERIFIED_APIS.md#m6-shared-teacher-hook-and-optional-mode-a)
for the exact formula and source paths. This is not full-vocabulary JSD or KL.

## Settings, evidence and limitations

[Small config](../configs/opsd_mode_a_small.toml) and
[27B config](../configs/opsd_mode_a.toml) are project configs, not upstream `rl`
TOMLs. Their exact keys are documented in VERIFIED_APIS. Relative config paths
resolve from the TOML directory. `--check` is read-only and sends no requests.
CLI exits: 0 ready/completed, 1 run error, 2 prerequisites unmet. Existing output
directories are never overwritten.

Each attempted ready run writes `run.json` (config/provenance/timestamps),
`requests.jsonl`, harness `trajectories/`, original `rollout.json` token records,
and `smoke.json` (status/kind/metrics/error type). Success adds `adapter.pt` and
its SHA256. This is a native parameter-name tensor checkpoint for inspection,
not a PEFT deployment package or a resume checkpoint with optimizer/RNG state.
Partial failures retain available evidence; cleanup is attempted independently.

`make test-m6` runs CPU tests using byte-identical installed prime-rl math files,
isolated from unrelated CUDA package initializers. A random tiny Qwen3.5 graph
checks full-attention forward/backward through its actual HF model class and
the pinned output head/LoRA/loss. It does not exercise pretrained loading,
hybrid linear-attention patches, CUDA, FSDP or compilation. Local Transformers
5.9.0 differs from the upstream locked server revision. Those tests are
explicitly labelled fixtures; they are not either required pretrained smoke.

The full-logit implementation intentionally makes no bounded-memory claim.
Both required real small/27B smokes remain **not run**; the original M6 runtime
acceptance criterion is deferred under the user's server-later instruction.
[PROGRESS](PROGRESS.md) records executed commands and blockers. The separate M7
entry records the later Mode B implementation and its verification.
