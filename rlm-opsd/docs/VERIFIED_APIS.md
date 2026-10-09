# Verified dependency APIs — M0

Verified on 2026-10-09 UTC against immutable source checkouts and installed files. **M0 setup code and local API checks are prepared; full Linux/CUDA installation is deferred at the user's request. The original full-install completion criterion has not been demonstrated.** See [PROGRESS.md](PROGRESS.md) for commands, failures, and unrun checks.

## Pins and verification boundaries

The package names differ from their import names. Pins live in [pyproject.toml](../pyproject.toml). Python is `3.12.12`; prime-rl requires `~=3.12.0`.

| Distribution / import | Exact source commit | Installed metadata version | Installation verified |
|---|---|---|---|
| `rlms` / `rlm` | `alexzhang13/rlm@d04208afbad29ca675ab13478c40ee8bebc84bfe` | `0.1.3` | Dependencies, import, installed source |
| `rlm-train` / `rlm_train` | Same RLM commit, `training/` subdirectory | `0.1.0` | Dependencies, import, offline subprocess REPL |
| `verifiers` / `verifiers` | `PrimeIntellect-ai/verifiers@58b119fa1b24eff85b74a75ccf3e132523b3c6c3` | `0.1.15.dev7` | Dependencies, import, adapter inheritance |
| `prime-rl` / `prime_rl` | `PrimeIntellect-ai/prime-rl@09e11c7527a242b9f150c7c4c71b1b96da66cb75` | `0.4.0` | **Source wheel only, installed with `--no-deps`; runtime unavailable** |
| `prime-rl-configs` / `prime_rl.configs` | Same prime-rl commit, `packages/prime-rl-configs/` | `0.4.0` | Dependencies, imports, selected Pydantic fields/values |

The verifiers commit is the exact `deps/verifiers` Git submodule recorded by pinned prime-rl. prime-rl is pinned to the parent of upstream change `eaf95997` that replaced the `teacher_tau` configuration. The latest branches were inspected and rejected: current verifiers no longer exports the adapter's original root API, and current prime-rl no longer uses that loss configuration. This is a source/API compatibility choice, not an end-to-end training certification. [Selection evidence](logs/m0/06-pin-candidate.log), [selected checkouts](logs/m0/07-selected-pins.log).

Two supporting sources are also fixed to prime-rl's own submodule/lock references:

| Package | Commit | Installed version |
|---|---|---|
| `PrimeIntellect-ai/renderers` | `8704f9d50252692a4a677177eb98d274f8d3ac5d` | `0.1.8.dev4` |
| `samsja/pydantic_config` | `73c1d84f7c359fa5fa3b7cfb946272352866efb7` | `0.3.0` |

prime-rl uses a commit archive to avoid automatic fetching of unrelated private/SSH submodules. Its installed archive SHA-256 is `d9e12cd1e597c333bcfbc6f6228a1e4b2efc42704a9fc366b95b84f9de0684c4`. The offline check compares every installed Python file from all five distributions to the corresponding checkout, checks Git heads and installation provenance, and prints exact signatures. [Smoke/provenance evidence](logs/m0/20-prime-source-and-smoke.log), [source paths, symbols, line numbers, and file hashes](logs/m0/23-source-catalog.log).

`requirements-m0-local.lock` resolves only the local inspection subset and its transitive dependencies, using an exclusion cutoff of 2026-05-28. It is **not** a Linux/CUDA runtime lock. The server script uses the pinned upstream `uv.lock` with `--frozen --no-dev --extra flash-attn`, then installs `requirements-m0-server-additions.lock`, resolved for Linux x86_64 against upstream's common dependency versions. The upstream lock export and the additions resolution succeeded locally; installation and CUDA imports have **not run** on a server. Source paths below are relative to each named upstream repository, available locally under `.deps/{rlm,verifiers,prime-rl}`. “Source verified” means read in the pinned source; it does not imply a model/server invocation.

The server target uses the upstream default `trainer.model.attn="flash_attention_2"` (`packages/prime-rl-configs/src/prime_rl/configs/trainer.py:199`). The lock selects torch `2.11.0+cu128`, vLLM `0.21.0+cu129`, and the FlashAttention 2.8.3 wheel built for torch 2.11/CUDA 12.8. These are upstream artifact pins, not a successful A100/H100 compatibility test. See the [server lock export](logs/m0/25-server-lock-export.log) and [Linux additions resolution](logs/m0/26-server-additions-check.log).

## RLM inference and training adapter

| Entry point | Exact source path / location | Verified contract |
|---|---|---|
| `from rlm import RLM` | `rlm/__init__.py`; `rlm/core/rlm.py:RLM`, line 41 | Public inference harness; import executed |
| `RLM.completion(self, prompt: str \| dict[str, Any], root_prompt: str \| None = None) -> RLMChatCompletion` | `rlm/core/rlm.py:326` | `prompt` is REPL context; `root_prompt` is the visible question. This exact annotation omits lists although `QueryMetadata` accepts them. No model completion executed. |
| `RLMChatCompletion` | `rlm/core/types.py:118` | Result fields include `response`, `usage_summary`, `execution_time`, `metadata`, `error` |
| `QueryMetadata(prompt)` | `rlm/core/types.py:265` | Produces `context_type`, `context_total_length`, `context_lengths`; accepts strings/lists/dicts. No `context_prefix` field. |
| `find_code_blocks(text: str) -> list[str]` | `rlm/utils/parsing.py:10` | Extracts blocks using regex `r"```repl\s*\n(.*?)\n```"`, DOTALL; strips each block |
| `build_rlm_system_prompt(system_prompt, query_metadata, custom_tools=None, root_prompt=None, orchestrator=True)` | `rlm/utils/prompts.py:211` | Returns system + metadata user messages; calls `system_prompt.format(custom_tools_section=...)`; appends `ORCHESTRATOR_ADDENDUM` when enabled |
| `from rlm_train import RLMTrainEnv` | `training/src/rlm_train/__init__.py`; `training/src/rlm_train/env.py:31` | Inherits `vf.MultiTurnEnv`; inheritance/import verified at runtime |

Relevant **RLM constructor** keys (not project YAML keys): `backend="openai"`, `backend_kwargs=None`, `environment="local"`, `environment_kwargs=None`, `depth=0`, `max_depth=1`, `max_iterations=30`, `max_budget=None`, `max_timeout=None`, `max_tokens=None`, `max_errors=None`, `custom_system_prompt=None`, `other_backends=None`, `other_backend_kwargs=None`, `persistent=False`, `compaction=False`, `compaction_threshold_pct=0.85`, `max_concurrent_subcalls=4`, `sampling_args=None`, `sub_sampling_args=None`, `orchestrator=True`, `user_prologue=None`. The complete constructor, including logger/tools/callback arguments, is recorded in the [signature log](logs/m0/20-prime-source-and-smoke.log).

The training package is a separate install; installing `rlms` alone does not install it. Its constructor is:

```python
RLMTrainEnv(
    backend_factory=None, max_iterations=30, sub_model=None,
    sub_sampling_args=None, custom_system_prompt=None, rubric=None,
    sub_llm_fn=None, sub_llm_fn_batched=None, user_prologue=None,
    bootstrap_code=None, orchestrator=True, **kwargs,
)
```

In `training/src/rlm_train/env.py`:

- `setup_state(self, state: State) -> None` (line 100) requires `state["info"]["context"]`, reads optional `info["root_prompt"]`, starts the backend at depth 1, and replaces `state["prompt"]` with metadata/history. `info.context` must hold the large input; putting it in the dataset's visible prompt would violate the project spec.
- `max_iterations` is passed to `MultiTurnEnv(max_turns=...)`. Passing `max_turns` directly raises `ValueError`. `sub_sampling_args` falls back to `{"max_tokens": 4096}`.
- `get_prompt_messages(self, state) -> Messages` (line 163) executes extracted REPL blocks, accumulates `rlm_history`, and sets `rlm_final_answer`/`final_env_response` when the backend returns an answer.
- `has_final_answer` uses `@vf.stop`; `cleanup_rlm` uses `@vf.cleanup`; `teardown_rlm` uses `@vf.teardown` (lines 224, 228, 241).
- `_format_one` (line 322) caps combined output at the module constant `_MAX_REPL_OUTPUT_CHARS = 20_000`; its notice reports omitted characters, not the project's required raw stdout length. This is not a configurable `stdout_max_chars` argument.
- `sub_model` changes the model name but uses `state["client"]`. It does not select a separate frozen server. The proxy receives `sub_llm_fn(prompt, state)` and `sub_llm_fn_batched(prompts, state)` overrides. Frozen-server routing remains later work.

### REPL/backend surface

`training/src/rlm_train/repl/base.py` defines `ReplBackend` and `ExecResult`. The async interface is `start(proxy_url: str, rollout_id: str, depth: int = 1) -> None`, `load_context(payload: Any, index: int | None = None) -> int`, `execute(code: str) -> ExecResult`, `stop() -> None`, and `bootstrap(code: str) -> None`. `ExecResult` contains `stdout`, `stderr`, `final_answer`, `execution_time`, `locals_keys`.

`SubprocessReplBackend` in `training/src/rlm_train/repl/subprocess.py:22` takes `python=None`, `worker_module="rlm_train.worker"`, `startup_timeout=30.0`, `request_timeout=1200.0`. It starts `python -u -m rlm_train.worker`, uses JSON messages over stdin/stdout, and propagates `RLM_TRAIN_PROXY_URL`, `RLM_TRAIN_ROLLOUT_ID`, `RLM_TRAIN_DEPTH`. The parent kills a worker on request timeout. An offline worker was actually started, given context, and used for persistent-variable computation and final-answer return. [Executed smoke](logs/m0/20-prime-source-and-smoke.log).

`training/src/rlm_train/worker.py:137` defines `Worker`. Its execution timeout is `exec_timeout_s`, defaulting from `RLM_TRAIN_EXEC_TIMEOUT_S` or 600 seconds; `_exec_with_timeout` uses `SIGALRM`/`setitimer`. `_setup_namespace` installs `context` (upon load), `llm_query`, `llm_query_batched`, `rlm_query`, `rlm_query_batched`, `SHOW_VARS`, and `answer`. Here `rlm_query` is an alias of the one-shot `llm_query`, not deeper recursion. No CPU or memory resource limits are imposed by this backend.

`training/src/rlm_train/proxy.py` defines `ClientHandle`, `SubLLMProxy`, and `_completion`. The production call is `handle.client.get_response(prompt=messages, model=model, tools=None, sampling_args=..., state={"trajectory": []})`. Only an override bypasses that network call; no sub-LLM service was invoked in M0. `RLMTrainRubric` in `training/src/rlm_train/rubric.py:13` accepts `correctness=None`, `weight=1.0`, `min_iterations=2`, `min_subcall=0`, `min_reward=0.0`, `gate_reward=False`, `**kwargs`; those upstream defaults are not project gate thresholds.

### Differences from SPEC that must not be assumed implemented

1. This upstream training adapter finishes via `answer["content"] = ...; answer["ready"] = True`. `_AnswerDict` is in `training/src/rlm_train/worker.py:121`. It does **not** parse assistant `FINAL(...)` or `FINAL_VAR(...)`. The RLM history shows that the answer-dict change preceded the addition of `training/`. M1 must adapt the required protocol; M0 does not change it.
2. `build_rlm_system_prompt` uses `str.format`, incompatible with passing the supplied literal-brace teacher manual directly. It also adds a default behavioral addendum. The prescribed student/teacher prompt construction is not provided by setting `custom_system_prompt` alone.
3. The metadata prompt emits type/total length, but omits the required chunk-length display and configurable prefix. Project `max_subcalls`, `max_subcall_chars`, sandbox CPU/memory limits, and trajectory JSON schema are not verified upstream configuration keys.

[Pinned RLM source](https://github.com/alexzhang13/rlm/tree/d04208afbad29ca675ab13478c40ee8bebc84bfe), [protocol evidence](logs/m0/14-protocol-source.log).

## verifiers interface

All paths in this section refer to verifiers commit `58b119fa1b24eff85b74a75ccf3e132523b3c6c3`.

| API | File / symbol | Contract verified |
|---|---|---|
| `vf.Environment` | `verifiers/envs/environment.py:93` | Constructor keys include `dataset`, `eval_dataset`, `system_prompt`, `parser`, `rubric`, `sampling_args`, `max_seq_len`, `score_rollouts=True`, `**kwargs` |
| `vf.MultiTurnEnv(max_turns=-1, timeout_seconds=None, **kwargs)` | `verifiers/envs/multiturn_env.py:39` | Async `setup_state`, `get_prompt_messages`, `env_response`, `rollout(input, client, model, sampling_args=None) -> State`; stop/cleanup hooks |
| `vf.load_environment(env_id: str, **env_args) -> Environment` | `verifiers/utils/env_utils.py:12` | Converts hyphens to underscores, drops namespace prefix, imports the module, calls its `load_environment(**env_args)` factory |
| `vf.Client.get_response(...)` | `verifiers/clients/client.py:Client.get_response` | Adapter client protocol; do not assume an `AsyncOpenAI.chat.completions` object can replace it directly |
| `State`, `TrajectoryStep`, `TrajectoryStepTokens` | `verifiers/types.py:429`, `:268`, `:227` | Trajectory tokens include `prompt_ids`, `prompt_mask`, `completion_ids`, `completion_mask`, `completion_logprobs`; messages use verifiers message types |
| `Environment.set_score_rollouts(False)` | `verifiers/envs/environment.py:1298` | Scoring branches call rubric dummy scoring when disabled, rather than computing reward; see lines 695–698, 725–728 |

`rlm_train` exports a class, **not** a `load_environment` factory. A project environment package/factory is still required before using it as a prime-rl environment ID. The built-in alternative `verifiers/envs/experimental/rlm_env.py` was located but not selected as the project's harness. [Pinned loader](https://github.com/PrimeIntellect-ai/verifiers/blob/58b119fa1b24eff85b74a75ccf3e132523b3c6c3/verifiers/utils/env_utils.py), [environment source evidence](logs/m0/12-environment-source.log).

## prime-rl entry points and configuration

The following console scripts are declared in pinned `pyproject.toml`; they are source verified. **They are not runtime verified:** executing `rl --help` fails on a missing runtime dependency. [Actual CLI failure](logs/m0/22-cli-check.log).

| Command | Entry point | File |
|---|---|---|
| `rl` | `prime_rl.entrypoints.rl:main` | `src/prime_rl/entrypoints/rl.py` |
| `trainer` | `prime_rl.trainer.rl.train:main` | `src/prime_rl/trainer/rl/train.py` |
| `orchestrator` | `prime_rl.orchestrator.orchestrator:main` | `src/prime_rl/orchestrator/orchestrator.py` |
| `inference` | `prime_rl.entrypoints.inference:main` | `src/prime_rl/entrypoints/inference.py` |
| `env-server` | `prime_rl.orchestrator.env_server.env_server:main` | `src/prime_rl/orchestrator/env_server/env_server.py` |

No SFT command was run. Config classes are distributed separately in `prime-rl-configs` but import through `prime_rl.configs.*`. Source prefix for every config path below is `packages/prime-rl-configs/src/prime_rl/configs/`.

| Exact TOML key | Source / symbol | Verified meaning/default |
|---|---|---|
| `deployment.type` | `rl.py:SingleNodeDeploymentConfig`, line 180 | `"single_node"` |
| `deployment.gpus_per_node` | `rl.py:BaseDeploymentConfig` | 8; bounds combined allocation |
| `deployment.num_train_gpus`, `num_infer_gpus`, `num_teacher_gpus` | `rl.py:SingleNodeDeploymentConfig` | Defaults 1, 1, `None` |
| `teacher_inference` | `rl.py:RLConfig`, `auto_setup_teacher_inference` line 934 | When teacher GPUs are requested, defaults to a copy of inference (or default inference config); sets teacher client/model and separate port; local single-node path |
| `orchestrator.teacher_model.model.name`, `.client.base_url` | `orchestrator.py:TeacherModelConfig`, line 883 | Teacher scoring model and client; `base_url` is a list in the auto-configured path |
| `trainer.loss.type` | `trainer.py:DefaultLossConfig`, line 684 | `"default"` selects sampled-token DPPO/distillation loss |
| `trainer.loss.teacher_tau` | Same class, line 692 | Nonnegative; default 0.0; teacher coefficient |
| `trainer.loss.adv_tau` | Same class, line 691 | Nonnegative; default 1.0; reward-advantage coefficient |
| `trainer.loss.kl_tau` | Same class, line 693 | Default `1e-3`; residual rollout/trainer regularization remains when `adv_tau=0` |
| `trainer.loss.dppo_mask_low`, `.dppo_mask_high` | Same class | Defaults 0.2, 0.2; probability-difference mask thresholds |
| `trainer.model.lora.rank`, `.alpha`, `.dropout`, `.target_modules`, `.modules_to_save` | `trainer.py:LoRAConfig`, line 111; `ModelConfig` | LoRA schema; rank default 16, alpha 32.0, dropout 0.0; no LoRA run performed |
| `trainer.optim.lr` | `trainer.py:BaseOptimizerConfig`, line 532 | Default `1e-6`; project starting value `2e-5` would be an explicit later setting |
| `orchestrator.rollouts_per_example` | `orchestrator.py:OrchestratorConfig`, line 1050 | Rollouts per example; project one-rollout setting not applied in M0 |
| `orchestrator.train.sampling.max_completion_tokens` | `orchestrator.py:TrainSamplingConfig`, line 73 | Per-turn output cap; `max_tokens` is a deprecated input alias |
| `orchestrator.train.sampling.extra_body` | Same class | Arbitrary server request options; no model-specific thinking key verified |
| `orchestrator.train.env` (array of tables) | `orchestrator.py:TrainConfig`, `TrainEnvConfig` | Environment entries with `id`, `name`, `args`, `ratio`, `num_workers`, etc. |
| `orchestrator.train.env[].args.score_rollouts` | `EnvConfig.args` → environment loader → `vf.Environment` | `False` can disable rubric scoring if the environment factory forwards it; this integration is source traced, not a training-run result |
| **`orchestrator.verification.enabled` — absent** | `OrchestratorConfig.model_fields` and source | The SPEC snippet does not load unchanged at this pin. No `verification` field exists; do not invent it. |

Runtime inspection confirmed the relevant field names, `DefaultLossConfig(teacher_tau=1.0, adv_tau=0.0)`, and sampling/env argument serialization. It did not validate a complete model-specific training configuration or start a teacher server. [`RLConfig` source](https://github.com/PrimeIntellect-ai/prime-rl/blob/09e11c7527a242b9f150c7c4c71b1b96da66cb75/packages/prime-rl-configs/src/prime_rl/configs/rl.py), [executed config checks](logs/m0/20-prime-source-and-smoke.log).

### Teacher logprob request and future hook location

The precise function is `async compute_teacher_logprobs(clients: list[vf.ClientConfig], model_name: str, samples: list[TrainingSample]) -> list[list[float]]` in `src/prime_rl/orchestrator/utils.py:81`. It creates one request per sample and gathers the results. The payload is:

```python
POST f"{base}/inference/v1/generate"
{
    "model": model_name,
    "token_ids": list(sample.prompt_ids) + list(sample.completion_ids),
    "sampling_params": {
        "max_tokens": 1,
        "temperature": 1.0,
        "top_p": 1.0,
        "prompt_logprobs": 1,
    },
}
```

It parses `vllm.entrypoints.serve.disagg.protocol.GenerateResponse`, maps empty/unscored entries to `0.0`, and takes `next(iter(entry.values()))` for each nonempty prompt-logprob dictionary. It does not select by the requested token ID explicitly. The native flattening/order must be validated against the actual server before relying on it in training. No HTTP request was executed here.

`src/prime_rl/orchestrator/orchestrator.py:581` calls the helper and line 587 assigns each returned list to `train_example.teacher_logprobs`. This is the identified **future M6 hook location**, not an implemented plugin: replace only student prefix token IDs with teacher prefix IDs, retain the suffix IDs verbatim, then map scores to student positions. Native code scores the student prompt without the privileged manual.

`src/prime_rl/transport/types.py:6` defines `TrainingSample` with `prompt_ids`, `prompt_mask`, `completion_ids`, `completion_mask`, `completion_logprobs`, `completion_temperatures`, `env_name`, optional `teacher_logprobs`, `advantage`, `reward`. `src/prime_rl/orchestrator/trajectories.py:interleave_rollout` (line 252) copies token arrays; its `extend_sample` masks newly appended prompt/observation tokens false. Later root-only masking and token alignment still need their own tests.

[Pinned teacher helper](https://github.com/PrimeIntellect-ai/prime-rl/blob/09e11c7527a242b9f150c7c4c71b1b96da66cb75/src/prime_rl/orchestrator/utils.py#L81).

### Exact sampled-token loss at this pin

Source: `src/prime_rl/trainer/rl/loss.py:default_loss_fn` and `compute_loss`. Define `s = trainer_logprobs`, `b = inference_logprobs`, `t = teacher_logprobs`, `A = inputs.advantages`, and `m = inputs.loss_mask`. The implementation computes:

```text
ratio = exp(s - b)
diff = exp(s) - exp(b)
invalid = where(A > 0, diff > dppo_mask_high, diff < -dppo_mask_low)
keep = m & ~invalid
adjusted_advantage = adv_tau * A + teacher_tau * stop_gradient(t - s)
sample_loss = sum(-keep * adjusted_advantage * ratio
                  + kl_tau * m * (s - b)^2)
packed_loss = sum(sample_loss over sequences) / loss_scale
```

The teacher term is included only if `teacher_logprobs is not None`. The invalid mask uses the **original** advantages before multiplying by `adv_tau` or adding the teacher term. Setting `adv_tau=0` does not remove the mask or the `kl_tau` term. The reported `teacher_kl` is the masked mean of `t - s`, a signed sampled logprob difference, not an evaluated full-vocabulary KL/JSD. This formula was source verified, **not numerically executed** in M0.

`setup_loss_fn` supports `trainer.loss.type="custom"`, `trainer.loss.import_path`, and `trainer.loss.kwargs` through `CustomLossConfig`. Its `LossInputs` exposes sampled logprobs, advantages, and mask, not full-vocabulary logits. This hook alone does not supply Mode B's teacher/student logits. Full-vocabulary JSD and the optional token gate are not implemented or run.

[Pinned loss implementation](https://github.com/PrimeIntellect-ai/prime-rl/blob/09e11c7527a242b9f150c7c4c71b1b96da66cb75/src/prime_rl/trainer/rl/loss.py), [captured source](logs/m0/08-prime-source.log).
# M1 additions: SPEC §2 adapter

The M0 pins above remain unchanged. New source locations and signatures were
checked in the [M1 source catalog](logs/m1/11-api-source-catalog.log); runtime
coverage is recorded in [PROGRESS.md](PROGRESS.md). Project usage and exact
resource-limit semantics are in [HARNESS.md](HARNESS.md).

## Upstream interfaces used by M1

Paths below are relative to the pinned repositories in `.deps/`, except where
explicitly identified as installed support packages. These include private
adapter hooks: repinning requires rechecking them and running the regression suite.

| Pinned source path and line | Verified interface / behavior | M1 use |
|---|---|---|
| `rlm/rlm/utils/parsing.py:10` | `find_code_blocks(text: str)` extracts triple-backtick `repl` blocks | Canonicalize complete fences, use reference extraction; independently mask all fences for finish parsing |
| `rlm/training/src/rlm_train/env.py:32` | `RLMTrainEnv.__init__(max_iterations, rubric, **kwargs)`; rejects `max_turns` | `RLMOpsdEnv` subclasses this adapter with `max_iterations=config.max_turns`, empty rubric, `score_rollouts=False` |
| `rlm/training/src/rlm_train/env.py:67` | `_proxy`, `_proxy_lock`, `_ensure_proxy`, `_teardown_proxy`; `cleanup_rlm` at 229, `teardown_rlm` at 242 | Reuse adapter lifecycle; select budget-aware proxy; close episode and owned client |
| `rlm/training/src/rlm_train/proxy.py:22` | `ClientHandle(client, model, sampling_args=None, record_call=None, max_concurrent=16, fake_query=None, fake_query_batched=None, state_ref=None)` | Register a separate frozen client, model, episode reference, concurrency |
| `rlm/training/src/rlm_train/proxy.py:93` | `SubLLMProxy.start/stop`, `.url`, `register/unregister`; `/rollout/{rollout_id}/llm_query` and `/llm_query_batched` | Real localhost worker-to-parent HTTP transport |
| `rlm/training/src/rlm_train/proxy.py:132` | `_handle_single`, `_handle_batched`, `_completion(handle, prompt, model)`; upstream singles do not use the batch semaphore | Override completion to enforce episode budget and a shared semaphore for singles/batches; ignore request-selected model; optional recursion flag on single endpoint |
| `rlm/training/src/rlm_train/worker.py:137` | `Worker(proxy_url, rollout_id, depth=1, exec_timeout_s=None)`, `_setup_namespace`, `_proxy_post`, `_llm_query`, `_llm_query_batched`, `load_context`, `_exec_with_timeout(code, ns)` | `HarnessWorker` inherits context loading, reference builtins, execution primitive and proxy calls; replaces capture/namespace persistence and removes answer-dict finishing and default recursion aliases |
| `rlm/training/src/rlm_train/repl/base.py:8` | `ExecResult(stdout, stderr, final_answer, execution_time, locals_keys)` and `ReplBackend` lifecycle | Preserve the adapter backend return contract; add character counts and error metadata in JSONL |
| `rlm/training/src/rlm_train/repl/subprocess.py:25` | `SubprocessReplBackend(python=None, worker_module, startup_timeout=30, request_timeout=1200)`; `_request`, `_send`, `_read_line`, `_kill_worker`; `_STREAM_LIMIT=16*1024*1024` | Subclass transport, launch dedicated process group, use configured wall watchdog, add variable-resolution request and resource monitoring |
| `verifiers/verifiers/envs/multiturn_env.py:135` | `add_trajectory_step(state, trajectory_step)` appends a step; `rollout` at 169 is final and checks stop conditions before the next prompt | Process immediately after step insertion so the final allowed turn executes; inherit the actual rollout loop |
| `verifiers/verifiers/envs/environment.py:491` | `get_model_response` reads `state['sampling_args']`; `init_state` at 553 resolves clients and normalizes input | Bound `max_tokens` in setup; retain caller decoding settings |
| `verifiers/verifiers/types.py:186` | `ResponseTokens.completion_ids`; `ResponseMessage` requires `finish_reason` and `is_truncated`; `Response` requires `id`, `created`, `model`, `message` | Correctly typed local fixtures; copy original provider completion IDs directly into JSON |
| `verifiers/verifiers/utils/response_utils.py:34` | `parse_response_message` preserves `reasoning_content`, `thinking_blocks`, tool calls; `parse_response_tokens` at 48 may clip IDs to `max_seq_len` | Retain provider message fields in root history; log full provider IDs separately from the clipped training representation |
| `verifiers/verifiers/utils/message_utils.py:128` | `normalize_messages(value, *, field_name='messages')` yields `vf.Message` objects | Return typed messages at the environment boundary |
| `verifiers/verifiers/clients/__init__.py:30` | `resolve_client(Client | ClientConfig)` returns an existing client or instantiates its configured implementation | Resolve loader-supplied frozen client configs; no root fallback |
| `verifiers/verifiers/types.py:1010` | `ClientConfig`: `client_type`, `api_base_url`, `api_key_var`, `timeout`, `connect_timeout`, `max_retries`, connection/header keys | Frozen endpoint supplied explicitly; default type is `openai_chat_completions` |
| `verifiers/verifiers/clients/client.py:113` | `Client.get_response(prompt, model, sampling_args, tools=None, **kwargs)` | Frozen async request with `state={'trajectory': []}`, `tools=None` |
| `verifiers/verifiers/clients/openai_chat_completions_client.py:243` | `get_native_response` maps `sampling_args['max_tokens']` to wire `max_completion_tokens`; `from_native_response` at 339 reads provider token IDs | Local HTTP fixture exercises the real client serialization and response conversion |
| `verifiers/verifiers/utils/client_utils.py:100` | `setup_openai_client` resolves endpoint config and uses `api_key_var`; absent key becomes `EMPTY` | Keys remain in parent client, excluded from worker environment |
| `verifiers/verifiers/decorators.py:101`, `:261` | `vf.cleanup` and `vf.teardown` annotate registered lifecycle handlers | Episode JSON/worker cleanup and proxy/owned-client teardown |

## Support packages

`psutil==7.2.2` is a new explicit project dependency, chosen to match the pinned
prime-rl runtime lock. `PyYAML==6.0.3` and `pytest==9.0.3` already matched both M0
locks and are now explicit M1 requirements. Installation is recorded in
[02](logs/m1/02-resource-dependency.log) and [09](logs/m1/09-layout-and-install.log).
`requirements-m1.txt` is installed after the M0 local lock, or with the runtime
constraints during server setup; it does not replace the M0 lock.

- Installed `psutil/__init__.py:775,951,1119,1130`: `Process.create_time()`,
  `children(recursive=True)`, `cpu_times()` (`user`, `system`, seconds),
  `memory_info()` (`rss`, `vms`, bytes). Parent watchdog sums live descendants'
  RSS and retains observed CPU totals; process-tree discovery is sampled.
- Installed `yaml/__init__.py:117`: `safe_load(stream)` for configuration.
- Installed `pydantic/main.py:427,493,694`: `BaseModel.model_dump`,
  `model_dump_json`, `model_validate`. Local version is the M0-locked 2.13.4;
  the server remains constrained by its M0 lock. No Pydantic repinning was made.

## Project entry points and config

- `rlm_opsd/__init__.py:load_environment(**kwargs)` → `RLMOpsdEnv`.
- `rlm_opsd/harness/env.py:RLMOpsdEnv`: required `frozen_client`, `frozen_model`,
  and upstream dataset/eval_dataset; optional `config` (model/dict/YAML path),
  `log_dir`, `system_prompt`, `prompt_variant`, `manual_version`.
- `rlm_opsd/harness/episode.py:Episode`: async context manager; `accept(text,
  token_ids)` executes one turn; `.trace`, `.messages`, `.log_path`, `.done`.
- `rlm_opsd/harness/protocol.py`: `context_metadata`, `parse_turn`,
  `truncate_output`; `trajectory.py:EpisodeTrace` validates the JSON shape.
- `rlm_opsd/harness/config.py:HarnessConfig.from_yaml(path)`; unknown keys and
  invalid budgets fail validation. `configs/harness.yaml` declares:
  `max_turns`, `max_tokens_per_turn`, `max_subcalls`, `max_subcall_chars`,
  `subcall_concurrency`, `subcall_timeout_s`, `subcall_max_tokens`,
  `subcall_chunk_chars` (reserved for M3 rendering), `prefix_chars`,
  `stdout_max_chars`, `enable_recursion`, `max_depth`, and
  `sandbox.{wall_time_s,memory_mb,cpu_time_s}`.

M0's listed protocol deviations are now adapted in project code. No upstream
source, trainer loss, teacher hook, template builder, task generator, or detector
was changed. Linux kernel address-space enforcement and real inference remain
not run; the local subprocess/HTTP tests are not GPU-run evidence.

# M2 additions: task generation and reserved-data adapters

M0/M1 dependency pins are unchanged; M2 adds no library dependencies. It uses
Python's standard library and the already pinned `PyYAML==6.0.3`
`yaml.safe_load(stream)`. Project symbols, signatures and file hashes are in
the [M2 catalog](logs/m2/15-source-catalog.log). Command and test results are in
[PROGRESS.md](PROGRESS.md); operational configuration and export contracts are
in [TASK_PIPELINE.md](TASK_PIPELINE.md).

## Project entry points verified by execution

| File / symbol | Contract |
|---|---|
| `rlm_opsd/tasks/__main__.py:main` | `python -m rlm_opsd.tasks {prepare,build,verify}`; `--config`, `--output` for build, `--manifest` for verify; JSON result and nonzero error exit |
| `rlm_opsd/tasks/models.py:TaskSpec`, `Task` | Seeded generation input; separate answer-bearing audit object; `Task.manifest(context_path)` and `Task.from_manifest(row, context)` |
| `rlm_opsd/tasks/generators.py:generate(spec, corpus=None)` | Six generated families, train/dev only; local seeded RNG; no benchmark substitution |
| `rlm_opsd/tasks/verify.py:verify_answer(task, corpus=None)` | Recompute from serialized context and task criteria, using offline classification annotations or ASTs; does not consult stored answer |
| `rlm_opsd/tasks/codec.py:render_records`, `parse_records` | Lossless plain/JSONL/CSV/log/Markdown records and whole-record list chunks |
| `rlm_opsd/tasks/sources.py:ClassificationCorpus.from_records`, `.from_banking_csv` | Dataset/revision/license provenance; TREC exclusion; checksum and duplicate/conflicting-label checks; explicit ambiguity policy |
| `rlm_opsd/tasks/prepare.py:checked_source`, `load_corpora`, `prepare_sources` | Checksum-pinned downloads/cache; split-specific classification imports; partial or full reserved-query/source index |
| `rlm_opsd/tasks/build.py:plan_specs(config)` | Stable split/cell seeds; explicit family weights and eligible grid exclusions |
| `rlm_opsd/tasks/build.py:build_pool(config, output_dir, *, corpora, heldout=None)` | Real `ProcessPoolExecutor` with `multiprocessing.get_context('spawn')`; ordered generation, answer verification, decontamination, atomic pool write |
| `rlm_opsd/tasks/build.py:verify_pool(manifest_path, *, corpora)` | Reload and independently verify every generated answer; benchmark answers explicitly excluded from this oracle |
| `rlm_opsd/tasks/build.py:load_tasks(manifest_path, *, split, inspection_only=False)` | Answer-free OPSD records, explicit split, coverage/manifest-hash guard, context checks; no trainer invocation |
| `rlm_opsd/tasks/decontam.py:HeldoutRecord`, `HeldoutIndex` | Benchmark query and source index; `.missing()`, `.load(path)`, `.write(path)`; query-only data cannot claim full coverage |
| `rlm_opsd/tasks/decontam.py:decontaminate(tasks, heldout, *, ngram_size, overlap_threshold)` | Normalized exact/near query and shared source/content removal; per-rule and per-split report |
| `rlm_opsd/tasks/heldout.py:adapt_heldout`, `load_heldout_snapshot` | Strict adapters for the five reserved benchmarks; always eval-only; JSON array or JSONL inputs |

`configs/tasks.yaml` keys are `seed`, `workers`, `size_buckets`, `structures`,
`encodings`, `families`, `splits`, `direct_read_max_chars`, `labels`,
`family_knobs`, `decontamination.{ngram_size,overlap_threshold}`,
`classification_sources`, `heldout_index`, `heldout_question_sources`, and
`heldout_snapshots`. Exact nested keys and generator knobs are documented in
TASK_PIPELINE.md and exercised by the CLI and planner tests. There are no
teacher, gate, loss or training config changes in M2.

## Pinned external data schemas

The following sources were read before implementing the corresponding import
contracts. Source discovery is captured in [01](logs/m2/01-public-source-discovery.log),
downloaded artifact hashes in [02](logs/m2/02-source-snapshots.log) and
[15](logs/m2/15-source-catalog.log). A schema inspection is not evidence that a
complete benchmark was downloaded or evaluated.

| Source and exact revision | Verified source path / fields | Execution boundary |
|---|---|---|
| [PolyAI-LDN/task-specific-datasets](https://github.com/PolyAI-LDN/task-specific-datasets/tree/57ec275d8078af65b7731c2a98be812d844a6d6b), `57ec275d8078af65b7731c2a98be812d844a6d6b` | `banking_data/train.csv`, `test.csv`: CSV `text,category`; repository `LICENSE` (CC BY 4.0) | Actual train/test bytes imported and used to generate dense task contexts; no TREC training source |
| [mit-oasys/oolong-pairs](https://huggingface.co/datasets/mit-oasys/oolong-pairs/tree/d1e1522b86ac0c169bbc890b0471408aaa29e8fa), `d1e1522b86ac0c169bbc890b0471408aaa29e8fa` | `questions.json`: `id,question,answer,type`; `README.md` specifies full `data/oolong-pairs-{context_len}.json` answers paired with matching `trec_coarse` validation context | Public templates actually imported for query checks. Full answer/context exports not imported. Card declares MIT. |
| [oolongbench/oolong-synth](https://huggingface.co/datasets/oolongbench/oolong-synth/blob/f0d59eaf0febf130664cfceb710436c8e3216b2b/README.md), `f0d59eaf0febf130664cfceb710436c8e3216b2b` | `README.md` dataset schema: `context_len`, `context_window_id`, `context_window_text`, `context_window_text_with_labels`, `dataset`, `question`, `answer`, `answer_type` | Adapter uses unlabelled context and filters `trec_coarse`; full export not imported. Operator must provide the source license with the export. |
| [Tevatron/browsecomp-plus](https://huggingface.co/datasets/Tevatron/browsecomp-plus/blob/144cff8e35b5eaef7e526346aa60774a9deb941f/README.md), `144cff8e35b5eaef7e526346aa60774a9deb941f` | `README.md`: `query_id`, `query`, `answer`, `gold_docs`, `evidence_docs`, `negative_docs`; document `docid,text,url`; official canary/SHA-256/XOR decryption recipe | Adapter accepts already-decrypted rows plus exactly 1,000 selected documents. No automatic decryption/document selection or full snapshot import was executed. |
| [zai-org/LongBench-v2](https://huggingface.co/datasets/zai-org/LongBench-v2/blob/2b48e494f2c7a2f0af81aae178e05c7e1dde0fe9/README.md), `2b48e494f2c7a2f0af81aae178e05c7e1dde0fe9` | `README.md`: `domain`, `sub_domain`, `context`, `question`, `choice_A`–`choice_D`, `answer`; original THUDM URL redirects to this namespace | Adapter filters `Code Repository Understanding` / `Code repo QA`; Apache-2.0 in card; full `data.json` not imported. |
| [NVIDIA/RULER](https://github.com/NVIDIA/RULER/blob/c3f5e3b4f87f97e048793bb510a3a6b19a46bf3a/scripts/data/synthetic/niah.py), `c3f5e3b4f87f97e048793bb510a3a6b19a46bf3a` | `scripts/data/synthetic/niah.py:284`: output `index`, `input`, `outputs`; the index is a needle position, so it is not used as a unique task ID | Single-needle adapter tested on fixtures. A real reserved S-NIAH seed/config/snapshot has not been imported; source inspection does not designate a new held-out set. |

The production source checksums are pinned in `configs/tasks.yaml`:

| Artifact | SHA-256 |
|---|---|
| BANKING77 train CSV | `b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b` |
| BANKING77 test CSV | `d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d` |
| OOLONG-Pairs question templates | `9d147c25ce727d09d35470ef267db59b3877132429b8b0269a46d941f252cada` |

All held-out adapters were exercised on explicit small fixtures. The actual
pool's decontamination ran only against the imported public question templates;
its report has `coverage_complete=false`, and normal train/dev loading rejects
it. This remains a data-coverage limitation, not a passing full-benchmark check.

# M3 additions: prompt sources, chat prefixes and token alignment

The user selected `Qwen/Qwen3.5-27B`. The exact source is
[`fc05daec18b0a78c049392ed2e771dde82bdf654`](https://huggingface.co/Qwen/Qwen3.5-27B/tree/fc05daec18b0a78c049392ed2e771dde82bdf654).
Only tokenizer/template/license artifacts were downloaded; no weights.
[Source download log](logs/m3/01-tokenizer-source.log).

| Artifact | Exact SHA-256 |
|---|---|
| `chat_template.jinja` → `prompts/chat_template.jinja` | `a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715` |
| `tokenizer.json` → `.deps/m3-tokenizer/tokenizer.json` | `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42` |
| `tokenizer_config.json` → `.deps/m3-tokenizer/tokenizer_config.json` | `316230d6a809701f4db5ea8f8fc862bc3a6f3229c937c174e674ff3ca0a64ac8` |
| `LICENSE` → `prompts/QWEN_LICENSE` | `50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32` |

Exact source paths, line numbers, signatures, package versions and hashes are in
the [M3 API catalog](logs/m3/07-api-catalog.log); final project hashes after review
fixes are in the [artifact audit](logs/m3/11-artifact-review.log). M0 library pins are unchanged.
The local lock provides Transformers 5.9.0, tokenizers 0.22.2 and Jinja2 3.1.6.
The server lock retains Transformers commit
`c1c34249fa27deefbd4a377dfbf883a39baf5c6d` (package version 5.5.0); its
`apply_chat_template` source was also inspected. Server execution remains unrun.

| Verified source / symbol | Contract used |
|---|---|
| Installed `transformers/tokenization_utils_tokenizers.py:TokenizersBackend.__init__`, exposed as `PreTrainedTokenizerFast` | `tokenizer_file=` loads the serialized backend directly; constructor accepts `bos_token`, `eos_token`, `pad_token`, `unk_token`, `clean_up_tokenization_spaces`. No remote model code needed. |
| Installed `transformers/tokenization_utils_base.py:PreTrainedTokenizerBase.apply_chat_template` and [server-pinned counterpart](https://github.com/huggingface/transformers/blob/c1c34249fa27deefbd4a377dfbf883a39baf5c6d/src/transformers/tokenization_utils_base.py) | `conversation`, `chat_template`, `add_generation_prompt`, `tokenize`, `return_dict`, `truncation`, `padding`, and template `**kwargs`; explicit `return_dict=False` gives IDs. Rendered prefix encoding uses `add_special_tokens=False`. |
| Same class, `.encode(text, add_special_tokens=False)` | Used only for new prefix/check fixture text, never by suffix alignment. |
| Pinned Qwen `chat_template.jinja` | Text-only system/user messages use `\|trim`; `enable_thinking=False` emits an empty thinking block, otherwise an open block; `add_generation_prompt=True` adds the assistant header. Both variants use this same file and flag. |
| Pinned verifiers `verifiers/clients/openai_chat_completions_client.py:get_native_response`, lines 243–317 | Passes `extra_body` through sampling arguments to the OpenAI-compatible request; `max_tokens` is renamed to `max_completion_tokens`. M3 supplies `extra_body.chat_template_kwargs.enable_thinking`. |
| Pinned prime-rl `packages/prime-rl-configs/src/prime_rl/configs/inference.py:chat_template`, line 84 | Accepts template text or a path, passed as vLLM `--chat-template`; deployment must use the pinned file. No inference/trainer config was instantiated or run in M3. |

## M3 project interfaces

- `rlm_opsd/prompts/templates.py`: `render_named(template, values)` performs one
  named-placeholder substitution pass; `PromptBuilder.load(source_dir=None,
  manual_version=None)` verifies registry/source hashes; `.build(query=...,
  context=..., config=...) -> PromptPair`; `.messages('student'|'teacher')`
  returns the exact SPEC message pair. The privileged manual only renders limits.
- `rlm_opsd/prompts/chat.py`: `PromptConfig.from_yaml(path=None)`;
  `.sampling_args(supplied)` binds/validates thinking without mutating input;
  `prepare_tokenizer(config)`; `load_tokenizer(config)`; `ChatRenderer(config,
  tokenizer=None).prefixes(pair) -> PrefixPair`. The optional tokenizer injection
  is for explicitly supplied callers/fixtures; default loading verifies artifacts.
- `rlm_opsd/prompts/alignment.py:build_teacher_sequence(student_ids,
  student_prefix=..., teacher_prefix=...)`: validates the recorded prefix and
  integer IDs, copies the suffix and asserts exact suffix equality. No tokenizer
  dependency; no M6 teacher-request hook or logprob remapping implemented.
- `rlm_opsd/prompts/__main__.py`: `python -m rlm_opsd.prompts prepare|check`,
  `--config`, `--thinking on|off`. `make prompts-check` exercises both modes.
- `configs/prompts.yaml`: exact keys are `model_name`, `revision`,
  `enable_thinking`, `template_path`, `template_sha256`, `tokenizer_path`,
  `tokenizer_sha256`, `tokenizer_config_path`, `tokenizer_config_sha256`.
- `prompts/versions.json`: `active_manual`, `student_sha256`,
  `manuals.<manual_vN>.{path,sha256}`; immutable snapshot and changelog in
  `prompts/versions/manual_v1.md` and `prompts/CHANGELOG.md`.
- `Episode` and `RLMOpsdEnv` now default to the registered prompt builder and
  `manual_v1`; `prompt_builder` selects a loaded bundle, and both also take
  `prompt_config`. Explicit custom system overrides need a `custom_...`
  version. User content is query-only; metadata appears in system content.

The [real-tokenizer check](logs/m3/06-real-qwen-tokenizer.log) verified prefix
construction and exact copied suffix IDs in both modes. The full remote server's
rendering/token-ID parity has not been executed. See [PROMPTS.md](PROMPTS.md) for
usage and the remaining deployment boundary.

# M4 additions: offline behavior analysis and token categories

M0 dependency pins and the M3 tokenizer/template revision are unchanged. M4 adds
no dependency. Installed Python is 3.12.12, Pydantic 2.13.4 and PyYAML 6.0.3.
Exact source paths, signatures and hashes are recorded in the
[M4 API catalog](logs/m4/12-api-catalog.log),
[category API inspection](logs/m4/categories-api.log), and
[metadata API inspection](logs/m4/trace-metadata-api.log).

| Source path / verified symbol | Contract used |
|---|---|
| Python 3.12.12 `lib/python3.12/ast.py`: `parse(source, filename='<unknown>', mode='exec', *, type_comments=False, feature_version=None)`, `walk(node)`, `dump(node, annotate_fields=True, include_attributes=False, *, indent=None)` | Produces AST with `PyCF_ONLY_AST`; statements are inspected, never executed. AST dump normalizes code for error recovery. |
| Python `lib/python3.12/tokenize.py`: `generate_tokens(readline)`, `TokenInfo(type,string,start,end,line)`, `TokenError`; `token.py`: NAME, COMMENT, ERRORTOKEN | Unicode row/column coordinates classify Python identifiers/comments; malformed suffixes retain conservative labels. |
| Installed `yaml/__init__.py:safe_load(stream)` | Reads explicit threshold YAML with SafeLoader; missing/null fields fail Pydantic validation. |
| Installed `pydantic/fields.py:Field`, `functional_validators.py:model_validator(mode='after')`, `main.py:BaseModel.model_validate`, `.model_dump` | Strict nonnegative geometry fields, exact list-length sum, no content/prefix field, backward-compatible optional trajectory geometry. |
| Existing `rlm_opsd/harness/protocol.py:parse_turn(text)` (M1 pinned RLM extractor underneath) | Fence-aware finish parsing, ignored suffix and malformed finish evidence. Repeated suffix parsing counts multiple finish forms. |
| Installed Transformers 5.9.0 `tokenization_utils_base.py:PreTrainedTokenizerBase.__call__`, `tokenization_utils_tokenizers.py:TokenizersBackend._encode_plus`, `._convert_encoding` | `return_offsets_mapping=True` yields `offset_mapping` copied from backend `Encoding.offsets`; used only for standalone cached-Qwen fixture verification. No rollout suffix is re-tokenized by category helpers. |

The actual [cached tokenizer smoke](logs/m4/categories-tokenizer-smoke.log)
exercises Unicode/overlapping offsets and category boundaries. The first API
inspection attempted the obsolete private `_batch_encode_plus` method, failed,
and was corrected by inspecting the installed `_encode_plus` path; the
[investigation log](logs/m4/categories-tokenizer-api-investigation.log) preserves
that failure. No server tokenizer parity, model inference or KL computation ran.

## M4 project entry points and config

- `rlm_opsd/detectors/config.py:DetectorConfig.from_yaml(path)`; every field is
  required: `probe_max_chars`, `dump_threshold`, `read_threshold`, `many_hits`,
  `subcall_max_chars`, `min_batch_chars`, `max_subcalls_expected`,
  `hand_copy_min_chars`, `dense_coverage_min`. Operational YAML is
  `configs/detectors.yaml`; fixture values are isolated under
  `tests/fixtures/detectors/fixture-config.yaml`.
- `rlm_opsd/detectors/evaluate.py:analyze_trajectory(trace, config, *,
  task_metadata=None)`; `facts.py:Extractor.block_facts(code, turn)` performs
  bounded abstract interpretation. Return keys are `task_id`, `family`, `domain`,
  `tags`, `size_bucket`, `detectors`, `task_tag_match`, `counts`,
  `coverage_lower_bound`, `unknown_reasons`, `facts`.
- `rlm_opsd/detectors/categories.py:classify_text_spans(text)`,
  `classify_token_offsets(text, offsets)`,
  `summarize_token_divergence(turns, *, metric_kind, top_k=10, context_chars=40)`.
  Turn inputs contain `turn_index`, `text`, `offsets`, `values`;
  `metric_kind` is `full_kl` or `sampled_logprob_delta`. Values are supplied, not
  calculated from model outputs here.
- `rlm_opsd/detectors/reports.py:aggregate_behavior(records)` and
  `write_behavior_report(records, output_dir, *, source_label=..., overwrite=False)`.
  Records contain `phase`, `trajectory_path`, `analysis`, optional `task_success`;
  output maps `markdown` and `csv` to paths. Missing phases are `not run`.
- `rlm_opsd/detectors/__main__.py:main(argv=None)` exposes
  `python -m rlm_opsd.detectors --config --manifest --output --source-label`,
  optional `--overwrite`. Manifest records contain `phase`, `trajectory_path`,
  optional `task_metadata` and `task_success`. Relative sources resolve from the
  manifest's directory.
- `rlm_opsd/harness/trajectory.py:ContextMetadataTrace`,
  `EpisodeTrace.context_metadata`, `EpisodeTrace.size_bucket`;
  `harness/episode.py:Episode.__init__` populates metadata geometry only.
  Legacy traces may omit both new fields.

[DETECTOR_USAGE.md](DETECTOR_USAGE.md) specifies applicability, unknown evidence,
coverage meaning, supported operations, limits and the plan-finish heuristic.
This is M4 only: no M5 teacher-gate target, training loss or monitoring sweep.

# M5 additions: teacher gate and revised OPSD architecture

The user's M5 steering makes **Mode B primary**, with a local frozen-base teacher
forward in the trainer. Mode A is optional. No teacher scoring server or teacher
scoring API is part of the revised architecture. The earlier upstream remote
teacher API catalog remains a source reference; it is not the selected path.
The M5 endpoints generate baseline/teacher-policy turns and frozen `llm_query`
responses only. No training implementation was added in M5.

## Generation clients and gate interfaces

Exact installed source, signatures and hashes were inspected before gate
implementation in [01-source-api.log](logs/m5/01-source-api.log). The M0 pins
remain unchanged.

| Verified source / symbol | Contract used |
|---|---|
| Pinned verifiers `verifiers/types.py:ClientConfig`, line 1010 | `api_base_url`, `api_key_var`, `timeout`, `connect_timeout`, `max_retries`, `max_connections`, `max_keepalive_connections`. Keys are referenced by environment-variable name, never stored as values in gate config. |
| `verifiers/utils/client_utils.py:_build_headers_and_api_key`, `_setup_openai_client_from_resolved`, `setup_openai_client` | Reads `api_key_var`; the PRIME_API_KEY special case can consult Prime config. M5 requires an explicitly named variable to exist, or uses an empty variable name for an unauthenticated endpoint (SDK placeholder EMPTY). |
| `verifiers/clients/client.py:Client.get_response(prompt, model, sampling_args, tools=None, **kwargs)` | Converts typed messages, obtains a native response, validates it and returns `Response`. Authentication/permission exceptions pass through upstream; M5 replaces provider exception text before crossing the harness/log boundary. |
| `verifiers/clients/openai_chat_completions_client.py:OpenAIChatCompletionsClient.get_native_response`, `.from_native_response`, `.close` | `max_tokens` becomes `max_completion_tokens`; sampling carries temperature, seed and `extra_body.chat_template_kwargs.enable_thinking`. Response exposes model, ID, usage, text/reasoning and optional token IDs. Original completion IDs are preserved if returned; no IDs are invented/re-tokenized. |
| Same source, `parse_tokens` inside `.from_native_response`, lines 427–495 | IDs require the response's `prompt_token_ids`, choice `token_ids`, and logprobs. M5 does not assume every compatible server supplies them; request provenance records `token_ids_available`. |
| Existing `harness/episode.py:Episode.__init__`, `.accept`, `.close` | Persistent REPL, frozen subcalls, budgets, geometry and JSON traces. Gate calls `.accept` on executable assistant content and preserves provider reasoning in the next request. Worker infrastructure errors are separated from measured budget/protocol failures. |
| Existing `tasks/build.py:load_tasks(manifest_path, *, split, inspection_only=False)` | Explicit `dev_behavior`; normal complete-coverage and manifest-hash checks remain enabled. Answers and verification annotations are stripped. M5 joins only size-bucket metadata, and requires every eligible family/bucket group to survive. |

Public M5 interfaces in `rlm_opsd/eval/`:

- `config.py:GateConfig.from_yaml(path)` resolves `manifest_path`,
  `harness_config`, `prompt_config`, `detector_config` from the config directory.
  Other keys: `base_model`, `revision`, `run_label`, `root_endpoint`,
  `frozen_endpoint`, `temperature`, `seed`, `request_timeout_s`,
  `episode_timeout_s`, `criteria`. Endpoint keys are `base_url`, `served_model`,
  `api_key_var`; credentials/query strings in URLs are rejected.
- `GateCriterion`: `metric` (D1–D18 or task_tag_match), `dimension`
  (overall/family/size_bucket/domain), `group` (including wildcard `*`),
  `direction` (min/max), `threshold`, `min_known`, `max_unknown_fraction`.
  Every acceptance value is user-supplied. Operational values remain null.
- `preflight.py:prepare_gate(config) -> GatePlan`,
  `check_readiness(path) -> {status, blockers, model_requests_sent}`.
- `decision.py:evaluate_gate(rows, criteria)` applies criteria only to teacher
  metric rows; statuses are passed, failed or inconclusive. Bounds are inclusive.
- `gate.py:run_gate(config, output_dir)` is async and runs paired generation.
  It writes `run.json`, `requests.jsonl`, `records.jsonl`, trajectories,
  `behavior.md/csv` and `gate.json/md`. Infrastructure errors override decisions
  and preserve partial evidence. Output directories are exclusive.
- `harness/episode.py:Episode(..., infrastructure_errors=None)` shares a list
  through recursive children. Setup, execute/resolve and cleanup failures record
  `task_id`, `stage`, `error_type`, `trajectory_path`; budget hits in assistant
  execution remain behavior. The gate rejects any recorded infrastructure error
  and links child evidence even when the root's final answer succeeded.
- `harness/sandbox.py:SandboxBackend._kill_worker`, `._request`: group SIGKILL is
  sent once after success/ESRCH and worker exit is awaited before surfacing a
  resource-limit EOF. This fixes a reproduced cleanup race without hiding an
  initial permission error or weakening child-process cleanup checks.
- `__main__.py:main(argv=None)`: `python -m rlm_opsd.eval teacher-gate --config
  ... --output ...`, optional `--check`. Exits: 0 passed/ready-check, 1 error,
  2 not run, 3 threshold failed, 4 inconclusive. `make teacher-gate` and
  `make teacher-gate-check` expose the entry point.

## Mode B: verified adapter residual-off mechanism in pinned prime-rl

Source pin: `09e11c7527a242b9f150c7c4c71b1b96da66cb75`. The
[source-verification log](logs/m5/10-mode-b-source-verification.log) records the
checkout HEAD, exact file hashes, numbered excerpts, AST assertions and equality
with installed source bytes. No trainer import/forward/GPU test was performed;
local PyTorch is absent.

| Pinned repository file / symbol | Verified behavior |
|---|---|
| `src/prime_rl/trainer/models/layers/lora/base.py:17–70`: `set_lora_num_tokens`, `get_lora_num_tokens`, `set_multilora_scaling(scaling_factors, reset_reference=False)`, `get_multilora_scaling()` | Process-global routing/scaling tensors. The normal setter uses `SCALING_FACTORS.copy_(scaling_factors)`; reset_reference=True replaces the reference instead. Getters assert initialization. |
| `src/prime_rl/trainer/models/layers/lora/__init__.py` | Exports those setters/getters and custom MultiLoRA module classes. No `disable_adapter` definition exists anywhere in pinned `src`. This trainer does not use a PEFT disable-adapter context. |
| `src/prime_rl/trainer/models/layers/lora/multi_linear.py:61–68,137–158`: `MultiLoRALinear.__init__`, `.forward(x)` | Caches `_lora_num_tokens` and `_scaling_factors`. Computes `base_out + per_token_scaling * lora_out`; per-token scale comes from repeat_interleave of cached global scaling. |
| `src/prime_rl/trainer/models/layers/lora/multi_moe.py:318,643,933`: forward methods of `MultiLoRAGroupedExperts`, `MultiLoRANonGatedGroupedExperts`, `MultiLoRAGptOssGroupedExperts` | Select adapter by token-count argmax, read scaling with `.item()`, multiply adapter residuals at each projection. All three variants use cached scaling references. |
| `src/prime_rl/trainer/runs.py:66–86`: MultiRunManager initialization | Initializes both global tensors before wrapping/model use. Modules and run manager retain references. Token counts must remain valid for each forward. |
| `src/prime_rl/trainer/lora.py:115–130`: `freeze_all_except_lora_and_specified(model, config)` | LoRA parameters and `modules_to_save` remain trainable; all others are frozen. Primary Mode B requires `modules_to_save=[]` and checks that non-LoRA weights truly remain frozen. |
| `src/prime_rl/trainer/model.py:1122–1162`: `forward(model, input_ids, position_ids, labels=None, temperature=None, routed_experts=None, ...)` | Calls the model and exposes `PrimeLmOutput`, including full `logits` when supplied by the output head. |
| `src/prime_rl/trainer/rl/train.py:403–444` | Sets per-microbatch LoRA token counts, then calls `forward`; the normal loop derives selected-token logprobs from logits when needed. Its existing teacher_logprobs input is not an in-trainer second teacher pass. |
| `packages/prime-rl-configs/src/prime_rl/configs/trainer.py:377–389`; `src/prime_rl/trainer/model.py:1038–1043`; `models/layers/lm_head.py:38–74,331–342` | Exact full-logit setting: `trainer.model.fused_lm_head_token_chunk_size = "disabled"`. `VanillaOutputLinear` emits logits; the integer-chunk `FusedOutputLinear` emits only selected-token logprobs and entropy. |

The source-backed residual-off sequence for later integration is:

1. Clone `get_multilora_scaling()` and save the original routing counts.
2. Install valid teacher-layout counts with `set_lora_num_tokens(...)` and set an
   all-zero scaling tensor using `set_multilora_scaling(...,
   reset_reference=False)`.
3. Run the privileged aligned teacher forward without gradients; teacher logits
   score the exact same suffix tokens at the mapped causal positions.
4. Restore both tensors **in place in finally**, along with any changed module
   modes/RNG state, before student backward/checkpoint recomputation.

Do not use reset_reference=True after construction: cached module references
would continue pointing at the old tensor. Serialize forwards because the state
is global across adapters/runs; a per-request teacher toggle is not thread-local.

**Verified limit:** zero scaling removes finite adapter residuals, but does not
skip adapter kernels or dropout. It is not an upstream computational bypass, and
NaN/Inf residuals can still invalidate logits. A robust later implementation must
validate finite residual/equivalence or add an explicit tested bypass, prove
base freezing, restore state on errors, and test FSDP/compile/checkpoint behavior
on the actual server. This source inspection does not claim those runtime tests
passed and does not add that integration in M5.

The user-authorized change is confined to [SPEC §6](SPEC.md#6-opsd-training):
Mode B primary, local teacher scoring, full-vocabulary masked JSD, Mode A optional,
generation-only endpoints. The task-independent y* and shared token-ID suffix
remain required. Sections outside §6 were preserved byte-for-byte.

# M6: shared teacher hook and optional Mode A

Scope confirmed by the user: shared in-trainer teacher hook plus optional Mode A;
JSD stays in M7. M0 source pins remain unchanged. The M5 descriptions above
record that milestone's state; M6 now adds the tested dense-adapter bypass and
CPU tensor execution. **Real small/27B pretrained smokes: not run.**

Evidence: [source check script](logs/m6/verify_source.py),
[signatures, hashes, config validation and primary-source URLs](logs/m6/22-source-verification.log),
[M6 tests](logs/m6/20-m6-green.log), [full suite](logs/m6/21-full-suite.log).
The script checks installed bytes against pinned prime-rl source before listing
symbols. CUDA imports/loading are not established by these source checks.

## Pinned runtime entry points used by the smoke

All prime-rl paths below are relative to commit
`09e11c7527a242b9f150c7c4c71b1b96da66cb75`.

| File / symbol | Verified contract and M6 use |
|---|---|
| `src/prime_rl/trainer/model.py:416`, `get_model(config, device=torch.device('cpu'), dtype=torch.bfloat16)` | No revision argument. M6 passes the locally cached exact-revision directory as `ModelConfig.name`, device CUDA 0 and BF16. The function disables parent/subconfig caches and applies Qwen3.5 patches. Pretrained loading and hybrid attention remain unexecuted locally. |
| `packages/prime-rl-configs/src/prime_rl/configs/trainer.py`, `ModelConfig`, `LoRAConfig` | Instantiated and validated keys: `name`, `impl='hf'`, `attn='eager'`, `seq_len`, `compile=None`, `ac=None`, `cp=1`, `ep=1`, `fused_lm_head_token_chunk_size='disabled'`; LoRA `rank`, `alpha`, `dropout=0`, `target_modules=['q_proj','k_proj','v_proj','o_proj']`, `modules_to_save=[]`. These are Python model fields; project smoke TOMLs are mapped explicitly to them. |
| `src/prime_rl/trainer/runs.py:490`, `setup_multi_run_manager(output_dir, max_runs, device, lora_config=None)` | Initialize after a one-process NCCL process group, before constructing adapters; M6 uses `max_runs=1`. Manager initializes cached global routing/scaling tensors. M6 explicitly sets `alpha/rank` in place rather than retaining the manager's sentinel scale. |
| `src/prime_rl/trainer/lora.py:132`, `apply_lora_to_model(model, config)` | Wraps target modules, registers adapters with the manager and calls `freeze_all_except_lora_and_specified`. M6 separately validates that only A/B parameters can require gradients and that every B starts at zero. |
| `src/prime_rl/trainer/models/layers/lora/multi_linear.py:38`, `MultiLoRALinear(base_layer, rank, n_adapters, alpha=32.0, dropout=0.0, use_grouped_mm=True)` | M6 supports exactly this dense class with one adapter. `reset_parameters` initializes B to zero. `.use_grouped_mm=False` selects unchanged `_run_lora_for_loop` ordinary matmuls on both Ampere/Hopper; no GPU runtime success is inferred. |
| `src/prime_rl/trainer/models/layers/lm_head.py:271`, `inject_prime_lm_head(model, chunk_size=None, fused_cross_entropy=False)` | Installs `VanillaOutputLinear`, preserves the original head weight, and patches model forward to consume `model.model(...).last_hidden_state`. M6 supplies explicit zero-based position IDs for each sequence. Actual CPU Qwen3.5 full-attention forward/backward through this head was tested. |
| `src/prime_rl/trainer/model.py:1122`, `forward(model, input_ids, position_ids, labels=None, temperature=None, ...)` | Returns `PrimeLmOutput` including float contiguous full logits for the vanilla head. M6 uses `logits[0, causal_positions, :]` and scales by sampling temperature before log-softmax. The wrapper itself belongs to the unexecuted full CUDA import path; CPU tests invoke the real head-patched model directly. |
| `src/prime_rl/transport/types.py`, `TrainingSample`, `MicroBatch` | Native schemas have `teacher_logprobs` but no privileged prefix/teacher-sequence fields. M6 uses a synchronous custom one-update loop around the actual upstream model/LoRA/loss functions. It does not claim integration of these prefixes into the native asynchronous transport or trainer loop. |

## Exact optional sampled-token objective

`src/prime_rl/trainer/rl/loss.py:14` defines `LossInputs(trainer_logprobs,
inference_logprobs, teacher_logprobs, advantages, loss_mask)`;
`LossOutputs(loss, metrics)` is at line 25 and
`default_loss_fn(inputs, loss_config)` at line 116. Config is
`prime_rl.configs.trainer.DefaultLossConfig` in the pinned config package.

For sampled target token n, define S = student logprob, T = teacher logprob,
I = rollout inference logprob, A = supplied reward advantage and m = loss mask.
The pinned code computes:

```text
r = exp(S - I)
d = exp(S) - exp(I)
invalid = where(A > 0, d > dppo_mask_high, d < -dppo_mask_low)
keep = m & ~invalid
A_eff = adv_tau * A + teacher_tau * stop_gradient(T - S)
native_loss = sum(-keep * A_eff * r + kl_tau * m * (S - I)^2)
```

The DPPO mask is computed using A **before** adding the teacher term. M6 passes
A=0, `adv_tau=0`, `kl_tau=0`, positive `teacher_tau`, and both DPPO bounds 1,
which prevents probability-difference clipping. After gathering only selected
assistant positions, it divides the native sum by their total count across
turns. Teacher and inference inputs are detached; the student receives the
gradient through r. Empty masks safely skip optimizer updates. The pinned
`teacher_kl` metric is the sampled T−S statistic, not full-vocabulary KL/JSD.

`training/teacher.py:frozen_teacher` is a **project context manager**, not an
upstream or PEFT API. It checks dense single-adapter/frozen-base invariants,
saves every module's training flag and any instance forward override, preserves
CPU/CUDA RNG via `torch.random.fork_rng`, zeroes/restores cached scale and token
count tensors in place, and replaces each dense adapter forward temporarily
with `base_layer(x)`. This avoids even NaN adapter computation. `finally` restores
state before student backward. A process-global reentrant lock covers the entire
training step. FSDP, compiled modules and other adapter classes are rejected.
Checkpointed CPU recomputation, exception restoration, reference identity and
unchanged base/teacher after LoRA updates are covered by executed tests.

## Generation records and policy convention

Pinned Verifiers `verifiers/utils/response_utils.py:parse_response_tokens`
returns `prompt_ids`, `prompt_mask`, `completion_ids`, `completion_mask`,
`completion_logprobs`, `is_truncated`, `overlong_prompt`. M6 rejects missing
records, malformed alignment and true clipping flags. A normal generation
`finish_reason='length'` is different from token-record truncation.
The existing `RLMOpsdEnv` uses the pinned Verifiers rollout/trajectory machinery
with rewards disabled and separate frozen leaf client.

`verifiers/clients/openai_chat_completions_token_client.py:get_native_response`
confirms `logprobs=True` and `extra_body.return_token_ids=True`.
M6 supplies these through the already verified ordinary chat client, which
passes extra-body keys and converts `max_tokens` to `max_completion_tokens`.
The harness also sets the pinned template's `enable_thinking` value.

`packages/prime-rl-configs/src/prime_rl/configs/orchestrator.py` confirms
`top_p` at request level and `top_k`, `min_p`, `repetition_penalty` in
`extra_body`; its native training defaults neutralize top-k/min-p too.
`configs/inference.py:565–566` sets the vLLM namespace
`logprobs_mode='processed_logprobs'`. The upstream lock selects vLLM
`0.21.0+cu129`. Its [SamplingParams source](https://github.com/vllm-project/vllm/blob/v0.21.0/vllm/sampling_params.py)
defines neutral top-p 1, top-k −1/0, min-p 0, repetition penalty 1 and
presence/frequency penalties 0. M6 sends these explicitly. Its
[model config](https://github.com/vllm-project/vllm/blob/v0.21.0/vllm/config/model.py)
defaults to raw logprobs, so a plain server must be configured for processed
logprobs. The project config declares this prerequisite; it does not remotely
verify or reconfigure the endpoint. Source bytes/hashes were retrieved in the
linked source log. The [pinned Qwen generation config](https://huggingface.co/Qwen/Qwen3.5-27B/blob/fc05daec18b0a78c049392ed2e771dde82bdf654/generation_config.json)
has top-k 20 and top-p 0.95, so leaving those server defaults would not match
M6's unrestricted temperature-scaled policy.

## Model pins, test environment and project entry points

Small family model: [Qwen/Qwen3.5-0.8B at 2fc06364715b967f1860aea9cf38778875588b17](https://huggingface.co/Qwen/Qwen3.5-0.8B/tree/2fc06364715b967f1860aea9cf38778875588b17).
`configs/prompts_small.yaml` pins:

- `prompts/chat_template_small.jinja`: SHA256 `273d8e0e683b885071fb17e08d71e5f2a5ddfb5309756181681de4f5a1822d80`.
- `.deps/m6-tokenizer-small/tokenizer.json`: `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.
- `.deps/m6-tokenizer-small/tokenizer_config.json`: `49e2b6e395f959f077f1e992b338919c0d4a9732fc6e613995e06557f843500c`.

Only tokenizer/template files were downloaded; no model weights. The original
27B revision/template remain unchanged. The small template differs from 27B;
its separate prompt/gate configs avoid treating them as identical artifacts.

`requirements-m6-local.txt` pins CPU torch 2.11.0, beartype 0.22.9, jaxtyping
0.3.9, loguru 0.7.3, networkx 3.6.1, setuptools 80.10.2 and wadler-lindig 0.1.7.
The existing local stack uses Transformers 5.9.0; server `uv.lock` uses torch
2.11.0+cu128 and Transformers 5.5.0 at
`c1c34249fa27deefbd4a377dfbf883a39baf5c6d`. M0 dependency files were not changed.
`tests/prime_cpu.py` checks byte equality then loads actual base/linear/head/loss
files while bypassing unrelated package initializers and the unused custom-loss
import helper. It does not replace the LoRA or loss math. Tiny random Qwen tests
cover full attention only, not pretrained loading/hybrid attention/CUDA.

Project entry points and exact config keys:

- `training/samples.py:samples_from_rollout(rollout, prefixes, *, max_seq_len)`
  returns immutable `AlignedSample(student_ids, teacher_ids, student_positions,
  teacher_positions, target_ids, inference_logprobs, temperature)` per root turn.
- `training/teacher.py:frozen_teacher(model, token_count, *, api=None)` and
  `teacher_logits(model, sample, forward_fn, *, api=None)` supply the shared hook.
- `training/mode_a.py:sampled_loss(student, teacher, inference, *,
  teacher_tau=1.0, loss_api=None)` calls the native objective;
  `ModeATrainer(...).step(samples)` returns loss, assistant_tokens,
  gradient_norm and updated. Only trainable adapter tensors enter AdamW.
- `training/config.py:OpsdConfig.from_toml(path)` keys: `mode='a'`, `stage`,
  `base_model`, `revision`, `prompt_config`, `gate_config`, `gate_dir`,
  `small_smoke_dir`, `max_seq_len`, `max_tokens`, `temperature`,
  `logprobs_mode='processed_logprobs'`, `seed`, `learning_rate`, `teacher_tau`,
  `max_grad_norm`, `lora_rank`, `lora_alpha`. Unknown fields are rejected.
- `training/backend.py:load_backend(config, snapshot, output)` owns its fresh
  one-process NCCL group and tears it down. `configure_adapters` validates the
  initial base equivalence and selects the ordinary-matmul adapter path.
- `training/runner.py:check_readiness(config)`, `prepare_smoke(config)`,
  async `run_smoke(config, output_dir)`: verify gate evidence/current provenance,
  training split, cached snapshot, Linux/CUDA and small-before-27B order.
- `training/__main__.py:main(argv=None)`: `python -m rlm_opsd.training smoke
  --config ... --output ...`, optional read-only `--check`.
  `make opsd-a`, `make opsd-a-check`, `make test-m6` wrap these interfaces.

[OPSD_MODE_A.md](OPSD_MODE_A.md) documents execution order and artifact semantics.
No `opsd-b`, JSD/token gate, monitoring/exit or GRPO code is implemented in M6.

# M7: primary full-vocabulary JSD and optional token gate

M7 implements SPEC §6.4–6.5 using the M6 local frozen teacher context. This
section supersedes the earlier milestone's statement that JSD/`opsd-b` are not
implemented. Mode B is primary and selected by default; optional Mode A remains
available. No pinned dependency/source revision changed and no package was
installed for M7.

Evidence: [initial source/signature inspection](logs/m7/01-source-api.log),
[reproducible verification script](logs/m7/verify_source.py),
[installed-source hashes/configs/numerical fixture](logs/m7/16-source-verification.log),
[74 M7 tests](logs/m7/15-m7-final.log). **GPU/pretrained small/27B execution and
peak GPU memory: not run / not measured.**

## Backbone and projection boundary

Source pin remains prime-rl `09e11c7527a242b9f150c7c4c71b1b96da66cb75`.
`src/prime_rl/trainer/models/layers/lm_head.py:345`, `_patch_model_forward`,
calls `model.model(input_ids=..., position_ids=..., ...)` and reads
`outputs.last_hidden_state` before invoking `model.lm_head`. M7's
`training/mode_b.py:backbone_hidden(model, input_ids, position_ids)` uses that
same backbone boundary with explicit positions and `use_cache=False`, returning
`[1, sequence, hidden]`. It does **not** call the model's full forward, the
language-model head, or the M6 `forward(...)["logits"]` path.

`training/backend.py:load_backend` still uses the verified pinned `get_model`,
run-manager initialization and `apply_lora_to_model`. For Mode A it retains
`inject_prime_lm_head(..., chunk_size=None)`; for Mode B it leaves the ordinary
linear head intact. `create_trainer(config, model, *, api, mode_a_forward=None)`
selects `ModeBTrainer` or `ModeATrainer`. Mode B validates an exact `nn.Linear`
head with frozen weight, no bias/instance forward override and no configured
softcapping. Other head transformations, sharding and compilation are unsupported.

Selected hidden rows are projected with installed torch 2.11.0
`torch.nn.functional.linear(input, weight, bias=None)`. Head dtype is preserved;
there is no full-vocabulary-weight FP32 copy. Ambient autocast is disabled for
this projection so recomputation uses the same arithmetic. Selected logits are
normalized in FP32 for FP16/BF16/FP32 inputs; float64 is retained for verification.
Finite input checks alone are insufficient: M7 also rejects normalization
overflow and temperature/reciprocal-temperature/gate-slope values outside the
working precision. The [overflow investigation](logs/m7/11-overflow-investigation.log)
and red/green regressions establish this behavior.

## Exact objective and recomputing backward

`training/jsd.py:masked_jsd_loss(student_logits, teacher_logits, mask, *,
target_ids=None, temperature=1.0, token_gate=False, gate_k=1.0)` is the dense
correctness interface. Inputs are matching floating `[tokens, vocabulary]`
tensors, a boolean `[tokens]` mask and optional aligned int64 target IDs.
Only selected target IDs need be inside the vocabulary; masked padding IDs
may be −100. The teacher is always detached.

```text
logS = log_softmax(student_logits / temperature)
logT = log_softmax(detach(teacher_logits) / temperature)
logM = logaddexp(logS, logT) - log(2)
JSD_n = 0.5 * sum_v(exp(logT) * (logT-logM) + exp(logS) * (logS-logM))
w_n = 1                                        # gate off
w_n = detach(sigmoid(k*(logT[target]-logS[target])))  # gate on
loss = sum_n(w_n * JSD_n) / selected_token_count
```

Beta is fixed at 0.5, all vocabulary entries contribute and log units are nats.
The gate is detached as a whole; its values do not replace the token-count
denominator. An empty mask returns a connected student zero, with no teacher
gradient. This is a project objective, not the native prime-rl sampled loss,
not the upstream `teacher_kl` statistic, and not a top-k approximation.

`training/jsd.py:chunked_jsd_loss(student_hidden, teacher_hidden, weight, mask, *,
target_ids=None, chunk_size=64, temperature=1.0, token_gate=False, gate_k=1.0)`
is the training interface. Hidden tensors are matching `[tokens, hidden]`;
weight is frozen `[vocabulary, hidden]`. It selects masked rows **before**
projection. `_ChunkedJSD(torch.autograd.Function)` saves only selected hidden
tensors, the head reference and target IDs. Forward projects/scores one row
chunk at a time. Backward rebuilds one chunk graph under `torch.enable_grad()`,
calls `torch.autograd.grad(value, hidden, grad_outputs=...)` without retaining
the graph, and writes each chunk into the student hidden gradient. Teacher,
head and IDs receive no gradients.

Installed torch source/signatures verified in the logs:

| File / symbol | Contract used |
|---|---|
| `torch/autograd/function.py:Function.forward`, `.backward`, `FunctionCtx.save_for_backward` | Custom forward returns scalar sum, saved tensors live until backward, backward returns one gradient/None per forward argument. No vocabulary activations are saved by this function. |
| Same source: `once_differentiable` | Explicitly marks the custom backward as first-order only. Higher-order differentiation is unsupported. |
| `torch/autograd/__init__.py:grad` | Recomputes the scalar chunk's VJP into a detached student hidden leaf, scaled by upstream gradient. Teacher/head are frozen. |
| `torch/autograd/graph.py:saved_tensors_hooks` | Test instrumentation records actual saved shapes; forward stores no sequence/vocabulary activations. |
| `torch/nn/functional.py:log_softmax`; native `functional.linear` | Stable log normalization in the selected working dtype; frozen native-dtype linear projection. Numerical tests verify against an independent probability-space formula and finite differences. |

The projection/loss workspace is O(chunk_size × vocabulary), in addition to the
existing head, selected hidden states/gradient and student backbone graph. M7
tests bound actual projection calls in forward and backward, and ensure no
vocabulary activations are saved between them. This does not establish a bound
on total backbone memory or measure GPU allocator peaks.

## Trainer, configuration and smoke evidence

`training/mode_b.py:ModeBTrainer(model, *, hidden_fn=backbone_hidden, api=None,
learning_rate=2e-5, max_grad_norm=1.0, chunk_size=64, token_gate=False, gate_k=1.0)`
exposes `.step(samples)`. It reuses immutable M6 `AlignedSample` records and
`FORWARD_LOCK`/`frozen_teacher`: student backbone first, privileged frozen-base
teacher second, then restored-state backward. Samples remain separate unpadded
turns; earlier history is context, never another current target. Per-turn means
are weighted by their selected counts so the overall denominator is total root
assistant tokens. Empty inputs do not run a model or optimizer; errors clear
gradients and restore routing before propagating. Returned metrics retain
`loss`, `assistant_tokens`, `gradient_norm`, `updated`.

Additional `OpsdConfig` keys in `training/config.py`:

- `mode`: `"b"` default, or `"a"`.
- `jsd_beta`: literal `0.5`; other values rejected.
- `jsd_chunk_size`: positive integer, default 64.
- `token_gate`: strict boolean, default false; true is rejected for Mode A.
- `token_gate_k`: positive finite float, default 1.0.

Existing keys remain `stage`, `base_model`, `revision`, `prompt_config`,
`gate_config`, `gate_dir`, `small_smoke_dir`, `max_seq_len`, `max_tokens`,
`temperature`, `logprobs_mode`, `seed`, `learning_rate`, `teacher_tau`,
`max_grad_norm`, `lora_rank`, `lora_alpha`. Nondefault `teacher_tau` is rejected
for Mode B because it belongs to the optional native sampled objective.
Model/tokenizer pins and generation settings remain unchanged.

`training/runner.py:objective_metadata(config)` records Mode B as
`kind='full_vocab_jsd'`, `beta`, `token_gate`, `token_gate_k`, `temperature`.
`smoke.json` adds this object and `mode`; `run.json` keeps the complete config
including chunk size. `verify_small_smoke` requires real small Mode B evidence
with the same objective and checkpoint hash before 27B Mode B. Mode A/legacy
evidence is not a Mode B prerequisite or substitute; existing Mode A behavior
remains compatible. Gate validity, data coverage, cached-weight and CUDA
requirements remain mandatory, with no fixture override.

New project configs are `configs/opsd_mode_b_small.toml` and
`configs/opsd_mode_b.toml`. `python -m rlm_opsd.training smoke` defaults to the
latter; `make opsd-b`/`opsd-b-check` accept `OPSD_B_CONFIG` and `OPSD_B_OUTPUT`.
`make test-m7` runs the new tests. [OPSD_MODE_B.md](OPSD_MODE_B.md) documents
execution order, artifacts and limits. M7 remains a one-update integration;
no upstream asynchronous transport, broadcast/resume, M8 or M9 was added.

## M8 OPSD-only monitoring and two-condition exit

User-revised scope: SPEC §7–9 and AGENTS M8/M9 now place GRPO-pool pass@k,
entropy and the mixed pass/fail criterion in M9. M8 implements behavior/KL and
retention only. These are project APIs; no upstream monitoring/exit API is
claimed. [Source inspection](logs/m8/03-source-api.log),
[reproducible verification](logs/m8/26-source-verification.log),
[verification script](logs/m8/verify_source.py), [usage](MONITORING.md).

### Pinned boundaries reused and verified

| Entry point / file | Verified contract used by M8 |
| --- | --- |
| Verifiers `58b119fa1b24eff85b74a75ccf3e132523b3c6c3`, `verifiers/envs/environment.py:Environment.rollout(self, input, client, model, sampling_args=None)` | Existing rollout state/trajectory token pipeline used through `RLMOpsdEnv`. Installed source equals pinned checkout. |
| Same commit, `verifiers/clients/openai_chat_completions_client.py:OpenAIChatCompletionsClient.get_response` and sampling conversion | Structured prompt messages, model, sampling args and state. `max_tokens` is translated to provider `max_completion_tokens` at lines 278–279; HTTP tests assert the emitted limit. `return_token_ids`/`logprobs` retain original root token records. No scoring request introduced. |
| Project `rlm_opsd/eval/gate.py:GateClient`, `rlm_opsd/harness/env.py:RLMOpsdEnv` | Separate base, checkpoint and frozen-leaf clients; returned model alias checked. Environment never sends task labels/context body to the root; actual HTTP/sandbox integration tests cover three phases. |
| Prime-rl `09e11c7527a242b9f150c7c4c71b1b96da66cb75`, `src/prime_rl/trainer/model.py`, `models/layers/lora/base.py`, `models/layers/lora/multi_linear.py` | Installed bytes verified equal to pinned checkout. Reuses existing M6 backend/adapter initialization and M7 backbone/head boundary without modifying upstream source. |
| Project `training/backend.py:load_backend`, `training/teacher.py:frozen_teacher`, `training/mode_b.py:backbone_hidden` | Load native single-adapter frozen-base model; use ordinary frozen head and selected hidden rows, serialize process-global routing under `FORWARD_LOCK`, bypass teacher LoRA, restore modes/routing. No optimizer step in monitoring. |
| Installed torch 2.11.0, `torch/serialization.py:load(f, map_location=None, pickle_module=None, *, weights_only=None, mmap=None, **pickle_load_args)` | `map_location='cpu', weights_only=True` reads the native adapter dictionary. Validate exact parameter names, shape, dtype and finiteness before in-place copies. Verify SHA-256 first. |
| Installed Transformers 5.9.0, `transformers/tokenization_utils_base.py:PreTrainedTokenizerBase.decode` / `.__call__` | Decode original completion IDs with `skip_special_tokens=False, clean_up_tokenization_spaces=False`; encode decoded text only for `return_offsets_mapping=True, add_special_tokens=False` and require exact ID equality. Unicode byte-piece overlap retained; special IDs mapped to `(0,0)`. Scored sequence IDs never come from this encode operation. |

Local Transformers remains 5.9.0; server-pinned Transformers is the existing
5.5.0 source revision documented in M6/M7. No installation or pin change was
made in M8. Local offset behavior is executed evidence, not a new claim of GPU
or server-template parity.

### Local scoring and metrics

`rlm_opsd/eval/scoring.py`:

- `load_adapter(model, path, checksum, *, api=None)` loads only complete native
  A/B parameters and preserves all base/head weights. No merge/publication.
- `token_offsets(tokenizer, ids)` returns `text`, unchanged `token_ids`, and
  offsets. Noncanonical round-trip tokenizations fail; no guessed alignment.
- `score_samples(model, samples, *, chunk_size=64, api=None)` returns per-turn
  `kl` arrays. Computes `sum_v pT(v) * (log pT(v) - log pS(v))` at each aligned
  root target using each sample's positive temperature. Selected hidden rows
  precede vocabulary projection. Both forwards and chunk projection run under
  no-grad; student adapter active, teacher adapter bypassed. No full-sequence
  vocabulary allocation, top-k approximation, entropy or GRPO-pool scoring.
  Probability arithmetic is FP32; tiny negative KL roundoff is clamped to zero,
  values below -1e-5 or nonfinite values fail explicitly.

`monitor_reports.py:summarize_divergence(turns, *, top_k)` consumes aligned
`turn_index,text,offsets,values,trajectory_path`. Reports token-weighted overall
KL, categories and turn index, plus highest-KL text positions with evidence.
Overall/turn KL includes all selected targets; category/top-text summaries
exclude and count special offsets. Existing M4 classification supplies lexical
categories; it does not re-tokenize the scoring suffix.

`metrics.py:score_answer(prediction, answer, answer_type)` and
`score_trajectory(trajectory, answer, answer_type)` implement exact stripped
scalar comparison, exact finite Decimal numeric equality, or scalar set F1.
Malformed RLM finishes score zero. Retention uses continuous F1 means; RLM task
success means score exactly one. These values never enter training rewards.
`RetentionItem.evaluable_gold` rejects unscorable gold before generation.

### Config, command and evidence APIs

`monitor_config.py:MonitorConfig.from_yaml(path)` resolves paths relative to
its YAML. Exact fields: `training_config`, `checkpoint`, `checkpoint_sha256`,
`checkpoint_step`, `eval_interval`, `run_label`, `student_endpoint`,
`endpoint_checkpoint_sha256`, `review_per_family`, `kl_top_k`, `temperature`,
`seed`. `student_endpoint` has `base_url`, `served_model`, `api_key_var` as in
M5. The endpoint-declared checkpoint hash must match local scoring. Config
forbids unknown keys and requires operator inputs; no retention keys are used.

`monitor.py:prepare_monitor(config)`, `check_monitor(path)`, and asynchronous
`run_monitor(config, output_dir)` validate the passed real gate, complete fixed
dev split, cached pinned weights, CUDA, checkpoint and endpoint declaration.
A non-due step returns `not_due`. A due run evaluates all three phases and
locally scores the `after` rollouts. Both A/B native checkpoints use the ordinary
head for evaluation; this does not change the selected training objective.
`monitor.json` inventories hashes of saved evidence, and `run.json` records
config/model/template/data/manual/checkpoint identity. Remote identity remains
operator-declared.

`ExitConfig.from_yaml(path)` fields: `evaluation_dir`,
`expected_checkpoint_sha256`, **required `retention_path`**,
`retention_max_tokens` (default 512), and `rules`. `ExitRules` requires
**`behavior_tolerance`**, `min_known`, `max_unknown_fraction`, and
**`retention_tolerance`**. All acceptance values and the retention path are
unset in `configs/exit.yaml`; the user chooses them after initial reports.
No GRPO readiness settings are accepted in these configs.

`exit.py:load_evaluation(directory, expected_checkpoint_sha256)` validates
complete real-kind evidence, inventory hashes, identity, all dev task/phase
pairs and completed generation requests; it recomputes detector/task-score/KL
summaries from source evidence. Fixtures cannot authorize exit.
`prepare_exit(config)` validates retention gold and checks current input hashes
against saved behavior provenance. Only the descriptive `endpoint_identity`
sentence is excluded from equality because monitoring extends its wording;
all input/model/manual/template provenance remains checked.

Async `exit.py:run_exit(config, output_dir)` calls
`retention.py:collect_retention(config, plan, output)` for paired base/checkpoint
generation through the pinned clients. Same prompt/template/thinking setting,
temperature and seed for each pair; answers stay out of requests. It saves raw
responses and scores, then `evaluate_exit(metrics, rules)` applies exactly
behavior agreement plus retention drop. Inclusive comparisons allow only
four binary64 ULPs at 1 for subtraction roundoff. Missing evidence is
inconclusive; request/cleanup failures are errors. Existing outputs are refused.

`make eval-behavior`, `make eval-behavior-check`, `make exit-check`,
`make exit-check-check`, and `make test-m8` dispatch these APIs. The two check
commands send no model requests; `exit-check` itself generates retention.
The checkpoint driver invokes monitoring each step; M8 does not extend the
M6/M7 smoke into an asynchronous training loop or implement M9.
