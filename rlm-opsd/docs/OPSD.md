# OPSD: full-vocabulary JSD

For multi-step training through prime-rl's async rollout/FSDP/vLLM loop, use
[`make opsd-train`](OPSD_TRAIN.md). This page documents the earlier one-update
smoke, which remains available as `make opsd`.

Both paths use QLoRA: frozen transformer linear weights are stored in 4-bit
NF4 with double quantization and dequantized on demand for BF16 computation.
Embeddings, norms, convolution parameters and the chunked JSD output head stay
frozen in BF16. Only the existing prime-rl LoRA adapters train. There is no
precision mode selector or dense-base training alternative.

OPSD uses the same frozen quantized initial base as
the teacher, with adapters bypassed for a second local backbone forward. No
teacher scoring server or scoring API is used.

The smoke performs one synchronous update to validate the objective before
server training. The multi-step job uses the same JSD objective inside the
native prime-rl trainer. Local verification covers CPU execution;
[PROGRESS](PROGRESS.md) links the checks and server prerequisites.

## Objective and memory

At each selected root assistant position, using the configured temperature:

```text
pT = softmax(teacher_logits / temperature)
pS = softmax(student_logits / temperature)
m = (pT + pS) / 2
JSD = 0.5 * KL(pT || m) + 0.5 * KL(pS || m)
loss = sum(selected_position_weight * JSD) / selected_position_count
```

All vocabulary entries contribute. Beta is fixed at 0.5, logarithms are natural,
and teacher tensors are detached. The optional token gate uses the recorded
target ID: `sigmoid(k * (log pT(target) - log pS(target)))`. That entire weight
is detached. Its default is off; `k` defaults to 1.0. Turning it on changes the
numerator, not the selected-token denominator. Empty masks contribute zero and
do not update the optimizer. No task answers/rewards enter this objective.

The standalone smoke calls the model backbone directly, obtains hidden states
and selects the aligned causal positions before vocabulary projection. It
uses the frozen ordinary linear head's weights, projecting at most
`jsd_chunk_size` selected rows at once. The teacher prefix still contains the
manual, and both sequences retain the exact recorded suffix IDs from M6.

A custom autograd function saves the selected student/teacher hidden states
and a reference to the existing head weights. Its backward recomputes one
projection/loss chunk, obtains the student hidden gradient, frees that chunk's
graph, and advances. Only then does the accumulated hidden gradient traverse
the student backbone. Adapter state is restored before this backward begins.
This supports first-order optimizer gradients, not higher-order differentiation.

Projection/divergence workspace scales as **O(chunk_size × vocabulary)**.
The frozen head weights, student backbone activations, selected hidden states
and their gradients are additional memory; total model memory is not bounded
by the chunk size. There is no full-sequence vocabulary tensor, full-head FP32
copy, retained graph per chunk, or top-k approximation. CPU tests observe real
projection shapes and saved tensors in both passes. Peak GPU memory and device
fit require measurements on the target server.

Projection uses the head's native dtype; normalization/divergence use FP32 for
FP16/BF16/FP32 inputs and retain float64 for numerical verification. Selected
nonfinite logits and arithmetic outside working precision fail explicitly.
For example, FP32-range logit subtraction or an unrepresentable reciprocal
temperature is rejected; probabilities are not clamped to manufacture a loss.

## Configuration

Start from [configs/opsd_small.toml](../configs/opsd_small.toml) and
[configs/opsd.toml](../configs/opsd.toml). Existing model pins, gate
requirements, generation conventions and sampling settings remain in force.

| Key | Meaning / default |
|---|---|
| `jsd_beta` | Must be `0.5` |
| `jsd_chunk_size` | Positive integer, default 64; selected positions per projection chunk |
| `token_gate` | Boolean, default `false` |
| `token_gate_k` | Positive finite gate slope, default `1.0` |

All other keys are listed in [VERIFIED_APIS](VERIFIED_APIS.md#m7-primary-full-vocabulary-jsd-and-optional-token-gate).
These smoke TOMLs configure the single JSD objective. Multi-step training uses
the native configuration in [opsd_train.toml](../configs/opsd_train.toml).

For gate on/off comparisons, copy the configs into distinct experiment configs
and use different output directories. Use the same fixed `dev_behavior` split
for the behavior comparison through `make eval-behavior`. A changed gate flag/slope or
temperature requires matching small-smoke evidence before the 27B smoke.

## Server execution order

Prepare the pinned Linux runtime with `make setup-server`, then follow
[TEACHER_GATE.md](TEACHER_GATE.md): complete decontamination, user-set
thresholds, passed current real gates, cached exact model weights, matching
generation endpoints/templates, original rollout IDs/logprobs, processed
logprob convention and Linux/CUDA BF16. Use `gate_small.yaml` for the small
model and `gate.yaml` for the 27B; each model requires its own passed real gate.

```bash
make opsd-check PYTHON=.venv-server/bin/python \
  OPSD_CONFIG=configs/opsd_small.toml
make opsd PYTHON=.venv-server/bin/python \
  OPSD_CONFIG=configs/opsd_small.toml OPSD_OUTPUT=reports/opsd-small

make opsd-check PYTHON=.venv-server/bin/python
make opsd PYTHON=.venv-server/bin/python
```

`python -m rlm_opsd.training smoke` defaults to the 27B OPSD config;
`--output` is required unless using `--check`. A 27B OPSD smoke requires a completed real
small OPSD smoke with matching beta, temperature, gate flag and slope, plus
the checkpoint hash. Missing/mismatched objectives and CPU fixtures cannot meet
this prerequisite. Changing chunk size alone does not change the objective.

Outputs preserve M6's provenance, generation requests, original tokens, native
LoRA tensor checkpoint and errors. `smoke.json` records the
`base_quantization` (`nf4`); older dense-base smoke evidence is rejected. It also records the
`objective` (`full_vocab_jsd`, beta, temperature, token gate and slope). Complete
settings, including chunk size, remain in `run.json`. A CPU runner test reports
`cpu_tensor_fixture`; a real pretrained smoke would report
`pretrained_model_smoke`. Existing outputs are never overwritten. Check-only
and rejected runs send no model requests and create no run directory.

Support remains eager, one process/GPU, one dense adapter, unpadded per-turn
sequences and a frozen ordinary linear head without bias or softcapping. The
normal-matmul adapter path targets A100/H100 compatibility, with pretrained
loading, Qwen hybrid attention and CUDA execution requiring server validation.
The actual tiny Qwen3.5 CPU tests use random weights and full-attention layers;
they establish the backbone/head boundary and adapter update, not model
behavior or server readiness. `make test-m7` runs the M7 tests.
