# M7: primary full-vocabulary JSD

Mode B is now the default OPSD mode. It uses the same frozen initial base as
the teacher, with adapters bypassed for a second local backbone forward. No
teacher scoring server or scoring API is used. Mode A remains optional.

M7 adds the objective and its selection to M6's **synchronous one-task,
one-update smoke**. It does not add asynchronous training, adapter broadcast,
resume, monitoring/exit checks or GRPO. GPU/pretrained execution remains
**not run**; see [PROGRESS](PROGRESS.md).

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

The implementation calls the model backbone directly, obtains hidden states
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
fit have not been measured.

Projection uses the head's native dtype; normalization/divergence use FP32 for
FP16/BF16/FP32 inputs and retain float64 for numerical verification. Selected
nonfinite logits and arithmetic outside working precision fail explicitly.
For example, FP32-range logit subtraction or an unrepresentable reciprocal
temperature is rejected; probabilities are not clamped to manufacture a loss.

## Configuration

Start from [configs/opsd_mode_b_small.toml](../configs/opsd_mode_b_small.toml) and
[configs/opsd_mode_b.toml](../configs/opsd_mode_b.toml). Existing M6 pins, gate
requirements, generation conventions and sampling settings remain in force.

| Key | Meaning / default |
|---|---|
| `mode` | `"b"` by default; `"a"` selects the optional native sampled objective |
| `jsd_beta` | Must be `0.5` |
| `jsd_chunk_size` | Positive integer, default 64; selected positions per projection chunk |
| `token_gate` | Boolean, default `false`; Mode B only |
| `token_gate_k` | Positive finite gate slope, default `1.0` |

All other keys are listed in [VERIFIED_APIS](VERIFIED_APIS.md#m7-primary-full-vocabulary-jsd-and-optional-token-gate).
The native sampled-objective `teacher_tau` is not a JSD weight: nondefault
values are rejected for Mode B. `teacher_tau` continues to work for Mode A.
These are project TOMLs, not native upstream `rl` configs.

For gate on/off comparisons, copy the configs into distinct experiment configs
and use different output directories. Use the same fixed `dev_behavior` split
for the later behavior comparison; no real comparison was run in M7 and the
M8 evaluation command is not implemented here. A changed gate flag/slope or
temperature requires matching small-smoke evidence before the 27B smoke.

## Server execution order

Use the pinned environment and prerequisites in [OPSD_MODE_A.md](OPSD_MODE_A.md)
and [TEACHER_GATE.md](TEACHER_GATE.md): complete decontamination, user-set
thresholds, passed current real gates, cached exact model weights, matching
generation endpoints/templates, original rollout IDs/logprobs, processed
logprob convention and Linux/CUDA BF16. Mode A training need not run first.

```bash
make opsd-b-check PYTHON=.venv-server/bin/python \
  OPSD_B_CONFIG=configs/opsd_mode_b_small.toml
make opsd-b PYTHON=.venv-server/bin/python \
  OPSD_B_CONFIG=configs/opsd_mode_b_small.toml OPSD_B_OUTPUT=reports/opsd-b-small

make opsd-b-check PYTHON=.venv-server/bin/python
make opsd-b PYTHON=.venv-server/bin/python
```

`python -m rlm_opsd.training smoke` now defaults to the 27B Mode B config;
`--output` is required unless using `--check`. Mode A make targets explicitly
select their existing configs. A 27B Mode B smoke requires a completed real
small Mode B smoke with matching beta, temperature, gate flag and slope, plus
the checkpoint hash. Legacy Mode A evidence and CPU fixtures cannot meet this
Mode B prerequisite. Changing chunk size alone does not change the objective.

Outputs preserve M6's provenance, generation requests, original tokens, native
LoRA tensor checkpoint and errors. `smoke.json` additionally records `mode` and
`objective` (`full_vocab_jsd`, beta, temperature, token gate and slope). Complete
settings, including chunk size, remain in `run.json`. A CPU runner test reports
`cpu_tensor_fixture`; a real pretrained smoke would report
`pretrained_model_smoke`. Existing outputs are never overwritten. Check-only
and rejected runs send no model requests and create no run directory.

Support remains eager, one process/GPU, one dense adapter, unpadded per-turn
sequences and a frozen ordinary linear head without bias or softcapping. The
normal-matmul adapter path targets A100/H100 compatibility, but pretrained
loading, Qwen hybrid attention and CUDA execution are not validated locally.
The actual tiny Qwen3.5 CPU tests use random weights and full-attention layers;
they establish the backbone/head boundary and adapter update, not model
behavior or server readiness. `make test-m7` runs the M7 tests.
