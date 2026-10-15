# Multi-step OPSD in prime-rl

`make opsd-train` runs the native prime-rl RL launcher, asynchronous rollout
scheduler, FSDP2 trainer, optimizer/scheduler, checkpoints, and vLLM LoRA updates.
The integration applies to **09e11c7527a242b9f150c7c4c71b1b96da66cb75**.
`make opsd` remains the separate one-update pretrained smoke.

Both commands now load frozen transformer linear weights as double-quantized
4-bit NF4 through bitsandbytes 0.49.0, with on-demand BF16 computation. Embeddings,
norms, convolution parameters and the JSD head remain frozen in BF16. Only
MultiLoRA parameters train. The teacher bypasses adapters over that same fixed
quantized base. Generation servers retain their existing base and receive the
same native adapter updates; NF4 introduces the usual quantization difference
between trainer and generation weights.

## Commands

From `rlm-opsd/`, after preparing the pinned Linux runtime:

```sh
# Readiness only: no GPU execution, model loading, or inference requests.
make opsd-train-check PYTHON=.venv-server/bin/python

# Start the native multi-step job on the training server.
make opsd-train PYTHON=.venv-server/bin/python

# Select an edited copy of the native training configuration.
make opsd-train PYTHON=.venv-server/bin/python OPSD_TRAIN_CONFIG=configs/my_opsd_train.toml
```

[configs/opsd_train.toml](../configs/opsd_train.toml) is the editable starting
configuration. Its top-level `[opsd]` section selects the existing pinned
model/gate/small-smoke settings; all remaining sections are native `RLConfig`.
`max_steps` controls the run length. `deployment.num_train_gpus` controls FSDP
workers, and `deployment.num_infer_gpus` / `inference.parallel.tp` control student
generation. Hardware counts are configuration choices, **not measured capacity**.
The default uses filesystem adapter synchronization through prime-rl: the trainer
gathers adapter shards, publishes a stable checkpoint, and the async scheduler
loads that adapter into vLLM before scheduling subsequent student policies.

The frozen `llm_query` generation endpoint comes from `gate.yaml`; keep it
serving the declared initial base model. Teacher **scoring** runs inside each
trainer rank and requires no teacher inference server or allocation.

Before starting, the launcher requires the real passed teacher gate, a successful
small-model OPSD smoke, cached weights at the pinned revision, and the
decontaminated train split. User-set acceptance thresholds remain in `gate.yaml`;
this change does not supply thresholds or bypass missing evidence. The CPU-only check reports the first
missing launch prerequisite without generating requests.

The launcher resolves the HF model to its immutable cached snapshot and supplies
the pinned template to native tokenizers and vLLM. It validates the final
configuration again after serialization, including native `run_default` paths.
For native checkpoint resume, set `[ckpt] resume_step = -1` in a config using the
same output directory and training settings. Full optimizer/scheduler state is
enabled in the shipped config. DCP stores packed NF4 parameters, quantization
buffers and adapters; the loader reconstructs the NF4 model before restoring
that state. Portable weight checkpoints contain `adapter_model.safetensors`
and `adapter_config.json` over the pinned original base. They no longer export
the dense base. Older dense-base training checkpoints are incompatible; start
a new output directory. GPU resume acceptance requires a checkpoint/restart check on the target server.

## Data and loss integration

- The environment factory loads `split='train'` through the existing
  decontamination checks. It supplies metadata-only prompts, disables scoring,
  and returns student/teacher prefix IDs in rollout `info`.
- Original recorded root token arrays are converted to one `TrainingSample`
  per turn. Re-tokenization, clipped tokens, answer labels, observations as
  targets, remote teacher logprobs, and SFT are rejected or excluded.
- The transport carries teacher IDs, causal positions, and prefix lengths.
  OPSD turns stay unpacked and unpadded. Native batch distribution supplies
  zero-mask dummy turns so every FSDP rank performs the same forward/backward
  schedule. Both sequences must fit their limits; teacher-prefix headroom is
  checked across the train split before launch.
- `trainer/model.py::setup_model` loads NF4 before installing the OPSD head, LoRA,
  activation checkpointing, and FSDP. Both passes call the outer wrapped model.
  The frozen teacher runs first; adapter forward methods, routing, scaling,
  module modes, and RNG are restored before the student pass.
- The student head calls the existing `chunked_jsd_loss` inside its FSDP forward,
  projecting only selected hidden rows. This retains exact full-vocabulary JSD
  without allocating complete sequence-by-vocabulary tensors. Teacher tensors
  remain detached; only LoRA parameters train. OPSD preserves RNG during
  activation-checkpoint recomputation.
- `trainer/rl/train.py` switches its normal loss branch to OPSD. Native
  optimizer steps, gradient clipping, scheduling, progress, broadcast, and
  checkpointing remain in the enclosing multi-step loop. Gradients normalize
  against the global assistant-token count, accounting for FSDP averaging;
  empty ranks still execute backward. `opsd/jsd/mean` reports the global
  token-mean objective, including the optional detached token gate.

The supported initial configuration is a single dense HF model/run, custom
MultiLoRA, FSDP data sharding, and optional activation checkpointing. Compilation,
FP8, context/expert parallelism, FSDP parameter CPU offload, multimodal models,
fake rollouts, trainable base modules, and remote teacher/SFT configurations
are rejected. Existing `optimization_dtype` and `reduce_dtype` defaults are
preserved for adapters and gradient reduction. Packed NF4 uses BF16 containers
without numeric dtype conversion; scales are checkpointed buffers. FSDP shards
the packed parameters using its existing wrapping. The smoke retains its
unsharded guard. Initial loading holds a quantized model per trainer GPU before
sharding; hardware fit requires measurement on the target server.

## Reproducible source patch

The dependency checkout is ignored by the parent repository. Its changes are
preserved in [prime-rl-opsd.patch](../patches/prime-rl-opsd.patch), with
before/after SHA-256 hashes in [prime-rl-opsd.json](../patches/prime-rl-opsd.json).
`make prime-opsd-patch` applies it once; subsequent calls verify it. A different
commit, partial patch, or unrelated tracked source change fails validation.
The launcher prepends both patched source and config-package paths to
`PYTHONPATH` for itself and all native subprocesses. It also selects native
entrypoints from the chosen Python environment. Installed wheels are left
unchanged and their pinned provenance continues to be checked independently.

```sh
# CPU inspection environment additions, if not already installed:
uv pip install --python .venv/bin/python -r requirements-m6-local.txt
make test-opsd-train
make test
```

CPU tests use actual pinned MultiLoRA, native transport/batching/configuration,
the chunked JSD implementation, and real PyTorch FSDP with Gloo. Local socket
access is required for Gloo and the existing HTTP fixtures. Those tests do not
establish CUDA/NCCL, vLLM, pretrained Qwen, or 27B memory/throughput results.
See [PROGRESS](PROGRESS.md#prime-rl-opsd-multi-step-integration) for executed
CPU checks and logs. CUDA/NCCL and vLLM acceptance requires server execution.
