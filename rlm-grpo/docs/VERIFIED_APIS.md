# GRPO dependency APIs

GRPO owns the source pins in `../pyproject.toml`. Its launcher requires a
pristine Prime-RL checkout and generates only its GRPO normalization overlay;
it does not load or apply the OPSD trainer patch. The setup script uses the
same frozen upstream runtime lock and unchanged RLM dependency snapshot as the
existing server setup, but creates a separate environment and source checkout.

Policy assets are local package data. The chat-template SHA-256 remains
`a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715`; the policy
API text SHA-256 remains
`1aa4f640928ecac721c42e2b33244abf7c5f681474c8208c71704747b67cbb1b`.
The existing finish parser and text normalization semantics were retained in
phase-owned modules, with no runtime imports from `rlm_opsd`.

The setup and install commands are source-derived, not executed results.

## Repository GRPO source contracts (October 15)

The existing RLM, verifiers, and Prime-RL pins are used by `rlm_grpo`.
The following were read in pinned source during implementation; they are source
contracts, not executed integration results:

| Source and symbol | GRPO use |
|---|---|
| `verifiers/envs/environment.py::Environment.__init__`, `init_state`, `get_model_response` | An environment requires a dataset or dataset builder, including child environments. Child rollouts inherit the parent dataset lazily and share its resolved policy client/model. State stores original response tokens via the native model-response pipeline. |
| `verifiers/envs/multiturn_env.py::rollout`, `add_model_response`, `add_trajectory_step`, `render_state` | `rollout` is final and reused unchanged. Execute REPL blocks in `add_trajectory_step` so the last allowed turn is processed. Cleanup runs before scoring; `render_state` priority 100 preserves the root completion before child branches are appended. |
| `verifiers/utils/save_utils.py::state_to_output` | Keeps `info` and requested `trajectory`/`sampling_args` columns; eligibility and original child tokens survive the environment-server boundary. |
| `rlm_train.repl.subprocess.SubprocessReplBackend` | Reuse JSONL request IDs, locking, watchdog and `ExecResult`. GRPO supplies Docker process startup, stdio child-call relay and remote process-group cleanup. |
| `rlm_train.worker.Worker` | Reuse builtins, Python execution watchdog, context and answer scaffold. Container adapter captures OS-level stdout/stderr and uses separate duplicated protocol descriptors. |
| `src/prime_rl/orchestrator/advantage.py::AdvantageInputs`, `AdvantageOutputs`, `compute_advantages` | Custom hook receives `rollouts: list[list[RolloutOutput]]`, returns a tensor `[num_problems, group_size]`. Native code assigns the resulting scalar advantage to each rollout. |
| `packages/prime-rl-configs/src/prime_rl/configs/orchestrator.py::CustomAdvantageConfig`, `EvalConfig`, `ZeroAdvantageFilterConfig` | Native custom `import_path`/`kwargs`, `eval_base_model`, eval interval, and enforced zero-advantage filtering. Native online difficulty filtering assumes 0/1 rewards, so GRPO disables it. |
| `src/prime_rl/orchestrator/trajectories.py::interleave_rollout` | Merges token-prefix extensions across agent branches, masks observation extensions, and preserves original completion IDs/logprobs. GRPO rejects missing original tokens before upstream retokenization fallback. |
| `src/prime_rl/trainer/rl/loss.py::LossInputs`, `LossOutputs`, `setup_loss_fn`, `compute_loss` | Custom hook returns a summed sample loss. Native `compute_loss` divides by trainer-provided `loss_scale`; a custom loss alone cannot change normalization. |
| `src/prime_rl/trainer/rl/train.py::train`, `trainer/parallel_dims.py::ParallelDims.get_mesh` | Native scale is local assistant-token count. GRPO's narrow overlay calls a global active-sequence/context-cap denominator, using the `dp` mesh and compensating FSDP averaging. `ParallelDims` has `pp`, `cp`, `ep`; this implementation requires them all to equal 1. |
| `src/prime_rl/trainer/ckpt.py::WeightCheckpointManager.get_run_adapter_state_dict`, `trainer/lora.py::save_lora_config`, `trainer/models/layers/lora/multi_linear.py::MultiLoRALinear` | Portable keys use `base_model.model.` and LoRA `A[r,in]`, `B[out,r]`; dense merge uses `alpha/r * B@A`. The existing OPSD patch exports these adapters for NF4 models. |
| `src/prime_rl/orchestrator/eval_utils.py::compute_pass_at_k` | Counts exact reward `1.0` successes, compatible with +1/−1 grading. |

Source links: [Prime-RL loss](https://github.com/PrimeIntellect-ai/prime-rl/blob/09e11c7527a242b9f150c7c4c71b1b96da66cb75/src/prime_rl/trainer/rl/loss.py),
[Prime-RL advantage](https://github.com/PrimeIntellect-ai/prime-rl/blob/09e11c7527a242b9f150c7c4c71b1b96da66cb75/src/prime_rl/orchestrator/advantage.py),
[verifiers rollout](https://github.com/PrimeIntellect-ai/verifiers/blob/58b119fa1b24eff85b74a75ccf3e132523b3c6c3/verifiers/envs/multiturn_env.py).
No pins changed. Syntax/TOML parsing and static source review only; Docker,
native config imports, merges, tests and GPU training **not run**.

