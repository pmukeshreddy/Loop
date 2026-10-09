# SPEC: RLM behavior via OPSD, then GRPO

## 1. Objective and phases

| Phase | Teaches | Signal | Labels |
|---|---|---|---|
| Teacher gate | Nothing; it validates y\* | Behavior detectors | None |
| OPSD | RLM behavior (how and when) | Per-token divergence to the privileged teacher | None |
| GRPO | Correct answers | Task reward | Answers / tests |

**Training targets the root model only.** Leaf sub-calls are general-purpose LLM requests; the hard part is learning to operate as the root.

---

## 2. RLM environment

Base the harness on `alexzhang13/rlm` (the paper's reference implementation) and its `training/` verifiers environment.

### 2.1 Episode initialization

**REPL namespace contains:**
- `context`: the task input, as either a `str` or a `list[str]`.
- `llm_query(prompt: str) -> str`: routes to the sub-call server (the frozen initial model).
- Recursion depth defaults to 1. Depth > 1 (`rlm_query`) is a config flag, off by default.

**The root model receives only metadata, never the context itself:**
- `context_type`
- `context_total_length` (chars)
- `context_lengths` (per-chunk lengths if a list)
- `context_prefix` (the first `prefix_chars` characters, configurable)

### 2.2 Turn loop

1. The root model generates a turn.
2. Extract the ```` ```repl ```` blocks.
3. Execute them in the persistent namespace.
4. Capture stdout and stderr, including tracebacks.
5. Truncate to `stdout_max_chars`. Append a notice with the full output length when truncated.
6. Return the result as the observation message.

### 2.3 Finish

- `FINAL(answer)` or `FINAL_VAR(name)` appears in assistant text outside code blocks.
- `FINAL_VAR` must name an existing variable. If it doesn't, return a protocol-error observation, log `finish_error`, and continue.
- Text after the finish token is ignored and logged.

### 2.4 Budgets (all in `configs/harness.yaml`)

- `max_turns`
- `max_tokens_per_turn`: leave headroom when thinking mode is on.
- `max_subcalls`
- `max_subcall_chars`
- `subcall_concurrency`
- Sandbox wall time, memory, and CPU limits.

### 2.5 Sub-call server

- Serves the frozen initial weights. It can share the teacher inference server in Mode A.
- Async-capable.
- Logs every call: prompt chars, output chars, latency, and the turn index of the root call.

### 2.6 Trajectory log

One JSON file per episode:

```json
{
  "task_id": "...", "family": "...", "domain": "...", "tags": ["..."],
  "prompt_variant": "student|teacher",
  "manual_version": "v1",
  "turns": [
    {"assistant_text": "...", "assistant_token_ids": [], "code_blocks": ["..."],
     "stdout_raw_chars": 0, "stdout_truncated": "...", "error": null,
     "subcalls": [{"prompt_chars": 0, "output_chars": 0, "latency_s": 0.0}]}
  ],
  "final": {"type": "FINAL|FINAL_VAR|none", "value": "...", "error": null},
  "budget_hits": {"max_turns": false, "max_subcalls": false},
  "timings": {}
}
```

---

## 3. Prompts

### 3.1 Definitions

- **x (student, also used at deployment):** system = render(`prompts/student_system.md`), user = query.
- **y\* (teacher only):** system = render(`prompts/student_system.md`) + `"\n\n"` + render(`prompts/teacher_manual.md`), user = the same query.

So y\* is the exact x API block followed by the rules, the worked examples, and the closing cue. It is task-independent and contains no answers.

### 3.2 Template variables and rendering

Placeholders:

`{context_type} {context_total_length} {chunk_info} {context_prefix} {subcall_max_chars} {subcall_chunk_chars} {stdout_max_chars} {max_turns}`

- `{chunk_info}` is `", split into N chunks with lengths [..]"` when `context` is a list. Otherwise it is empty.
- `{subcall_chunk_chars}` is set in `configs/harness.yaml`, as a fraction of `subcall_max_chars`.
- Render by replacing only these named placeholders. Do not use `str.format`: the manual contains literal braces in code and JSON.
- Test that no unreplaced placeholder remains.

### 3.3 Chat template

- Use the same chat template and the same thinking-mode setting for both prompts. Only the system content differs.
- Pin the template and test that it renders identically, apart from the system content.

### 3.4 Token alignment (required test)

```
S_prefix = render(system=x_system, user=query) up to the first assistant token
T_prefix = render(system=y_system, user=query) up to the first assistant token
student_ids = S_prefix + suffix            # suffix = all assistant turns + observations
teacher_ids = T_prefix + student_ids[len(S_prefix):]
assert teacher_ids[len(T_prefix):] == student_ids[len(S_prefix):]
```

Build both sequences from token IDs. Never re-tokenize the suffix.

### 3.5 Versioning

Version `teacher_manual.md` (`manual_v1`, `manual_v2`, …) and keep a changelog. Record the version in every trajectory log.

---

## 4. Task pool

See `docs/TASKS.md`.

- One mixed pool across all families, using one shared y\*.
- Every task carries domain and behavior tags.
- Extra-tool domains add a short addendum to both x (the API) and y\* (when to use it).

---

## 5. Teacher gate

**Inputs:** the `dev_behavior` split (TASKS.md §4) and the base model.

**Runs:**
1. Base model generating with x: the baseline.
2. Base model generating with y\*: the teacher-as-policy, which is the target behavior.

**Output:** a detector report for both runs (DETECTORS.md §4), broken down by family and size bucket.

**Iterate:** if run 2 misses thresholds in `configs/gate.yaml`, edit `teacher_manual.md`, bump the version, and rerun. OPSD starts only after the gate passes.

**Check coding ability:** the gate report includes the syntax-error rate. A model without enough coding ability will struggle as an RLM.

---

## 6. OPSD training

**Primary path: Mode B, with teacher scoring inside the trainer.** The teacher is
the same model's frozen initial base weights with the LoRA contribution disabled
for a second forward pass. It supplies full-vocabulary logits for masked JSD.
There is no teacher inference server and no teacher scoring API call. Inference
endpoints are used only for generation: student rollouts, the baseline/teacher
policy runs in §5, and `llm_query` sub-calls. Mode A is an optional sampled-token
objective using the same local teacher-scoring mechanism.

### 6.1 Notation and frozen-base invariant

- x: student context. y*: privileged context. ŷ: the student's rollout.
- Student: `p_S(· | x, ŷ<n)`, the initial base plus trainable LoRA.
- Teacher: `p_T(· | x, y*, ŷ<n)`, the initial base with LoRA disabled for scoring.
- All non-LoRA parameters remain frozen, including embeddings and the output
  head. `modules_to_save` must be empty; otherwise disabling LoRA would expose
  updated weights instead of the fixed initial teacher.
- The loss covers root assistant tokens only. Teacher computation runs without
  gradients; only the student pass contributes gradients.

### 6.2 Aligned sample construction

- Generate one student rollout per task. Both forward passes score the same
  recorded rollout token IDs and assistant positions; never generate a separate
  teacher answer or re-tokenize the suffix.
- Keep `S_prefix + suffix` for the student. Construct `T_prefix + suffix` for the
  teacher using §3.4's exact token-ID replacement. The privileged teacher prefix
  remains different; the scored suffix is identical. “Same aligned sequence”
  refers to these shared rollout tokens, not removal of y*.
- Build each sequence's position IDs, packing/attention metadata and causal
  next-token index mapping for its own prefix length. Assert shared suffix IDs
  and map every teacher logit position to the corresponding student target.
- Mask = root assistant target tokens only. Exclude system/user tokens,
  observations, padding and sub-call tokens from the objective.

### 6.3 Mode A: optional sampled-token objective

Mode A is optional, not a prerequisite for Mode B. It can reuse prime-rl's native
sampled-token distillation loss with `teacher_tau` enabled and `adv_tau = 0`.
Obtain teacher logprobs by gathering the recorded target token from the trainer's
local frozen-base teacher logits after alignment. The native pinned training
loop currently consumes `micro_batch["teacher_logprobs"]`; supplying these locally
requires an explicit integration change.

Do not configure `deployment.num_teacher_gpus`, a teacher endpoint, or an
orchestrator teacher-logprob request for this architecture. The upstream remote
teacher request path is source reference only, not the selected execution path.
Record the sampled-token formula from the pinned source when implementing this
optional mode; sampled-token values must not be reported as full-vocabulary JSD.
Verification/rewards remain disabled during OPSD.

### 6.4 Mode B: primary full-vocabulary JSD

1. Forward the student sequence with its LoRA adapter active.
2. Perform a second, no-gradient teacher forward using the same model instance,
   the aligned privileged sequence, and the adapter contribution disabled.
   Restore adapter/token-routing state and module training flags before student
   backward or activation-checkpoint recomputation. Serialize this state change;
   prime-rl's LoRA scaling state is process-global, not request-local.
3. Detach teacher logits and compute `JSD_β(p_T ‖ p_S)` with β = 0.5 over the full
   vocabulary at the aligned masked positions. Normalize over selected root
   assistant positions; an empty mask contributes zero safely.
4. Chunk the vocabulary projection and divergence work along masked sequence
   positions to bound memory. Merely chunking a loss after materializing both
   complete `[batch, sequence, vocabulary]` tensors does not bound their peak
   allocation. A top-k approximation, if later added, is an explicit optional
   fallback and must be labelled as approximate.

**Pinned adapter mechanism.** At prime-rl commit
`09e11c7527a242b9f150c7c4c71b1b96da66cb75`, training uses custom `MultiLoRA`
layers, not a PEFT `disable_adapter()` context manager. The source-backed
mechanism for zeroing the adapter residual is
`get_multilora_scaling()` / `set_multilora_scaling(tensor, reset_reference=False)`
in `prime_rl.trainer.models.layers.lora.base`. Save a clone of the current
scaling tensor, set an all-zero tensor in place for teacher scoring, and restore
it in `finally`. Keep valid token counts via `set_lora_num_tokens`; adapt them to
the teacher's packed sequence and restore the student counts too. Modules cache
these tensor references, so replacing global references after model construction
is not a valid toggle.

Zero scaling removes finite adapter contributions from the output; upstream
still executes adapter kernels and dropout. It is not a computational bypass,
and zero times a nonfinite adapter result is not safe teacher output. The later
trainer integration must either verify finite residuals/equality or add a tested
true bypass, preserve dropout/RNG and module modes, and verify restoration,
checkpointing, FSDP and compilation behavior. No such trainer context manager is
implemented or GPU-validated in M5. Exact source paths and limitations are in
`docs/VERIFIED_APIS.md`.

**Full logits.** The pinned `FusedOutputLinear` returns selected-token logprobs
and entropy, not full-vocabulary logits. For the initial correctness path,
`[trainer.model] fused_lm_head_token_chunk_size = "disabled"` selects
`VanillaOutputLinear`; `prime_rl.trainer.model.forward(...)` exposes `logits`.
A memory-bounded full-vocabulary projection path still needs implementation;
the upstream chunked sampled-logprob head is not a JSD substitute.

Required tests before deployment: identical distributions give zero JSD;
teacher tensors receive no gradients; masked/non-assistant positions contribute
zero; suffix/causal positions align across different prefix lengths; zeroed
adapter logits match an unadapted frozen base; all adapter/routing/mode state is
restored even on exceptions; student gradients remain valid through the second
forward and checkpoint recomputation. Then run a small-model smoke and the 27B
server smoke. M5 only verifies the source contract and generation-based gate.

### 6.5 Optional token gate (config flag, default off)

- Per-token weight, detached:
  `w_n = sigmoid(k * (log p_T(ŷ_n) − log p_S(ŷ_n)))`.
- Both logprobs come from the aligned in-trainer passes. No scoring API is used.
- This strengthens teacher-endorsed tokens and softens teacher rejections as a
  guard against multi-turn drift. Compare gate on/off on the same eval split.

### 6.6 Optional token-category weights

- Per-category loss weights for prose, code, comment and protocol tokens
  (DETECTORS.md §5).
- Default is all 1.0. Change only based on the token-category KL report.

### 6.7 Starting config (tune for 27B)

- Mode B is primary; Mode A is opt-in.
- LoRA rank in config; all non-adapter weights frozen; `modules_to_save = []`.
- lr 2e-5; 1 rollout per task; fixed initial-base teacher; β = 0.5.
- The mixed task pool from TASKS.md; no reward optimization or SFT stage.
- No teacher scoring server/GPU allocation. Generation servers retain the base
  model for the teacher gate and frozen leaf calls, and serve the student adapter
  for student rollouts once training begins.

The RLM paper's RL run used 20 max iterations and 4096 max tokens per turn.
Treat those as reference values, not requirements.

---

## 7. Monitoring

Every `eval_interval` steps, on the fixed `dev_behavior` eval split:

- **Behavior:** all detectors (DETECTORS.md), the syntax-error rate, and sub-call stats.
- **Divergence:**
  - `teacher_kl` overall,
  - KL by token category,
  - KL by turn index, to watch for drift.
- **Retention:** a small general-capability eval set chosen by the user.
- **Task success:** tracked, not optimized.
- **Manual review:** dump k readable trajectories per family into `review/step_<n>/`.

---

## 8. Exit criteria

Thresholds live in `configs/exit.yaml` and are set by the user. OPSD exits when both hold:

1. On `dev_behavior`, the student's detector rates under x are within tolerance of the teacher-as-policy rates under y\*.
2. The retention eval is within tolerance of the base model.
The behavior tolerance, retention tolerance, and user-selected retention dataset
path are required unset fields in `configs/exit.yaml`. The user fills these after
reviewing the teacher-gate and behavior-eval reports. Behavior evaluation can run
before retention is configured; the exit check cannot pass without retention.
GRPO-pool readiness is not an OPSD exit criterion.

---

## 9. GRPO handoff (after M8)

**Pre-GRPO readiness check (M9, before any GRPO step):**
- Measure pass@k and entropy on a sample of the GRPO pool.
- Require the fraction of tasks with an intermediate pass rate (not all-pass,
  not all-fail) to meet a user-set threshold.
- Run this check only in M9, after the two-condition OPSD exit check passes.

**Starting point and harness:**
- Start from the merged OPSD checkpoint.
- Use the same harness and the same x.

**Reward:**
- Task correctness, scored per `answer_type`.
- A malformed finish scores 0.

**Loss config:**
- `adv_tau = 1.0`.
- `teacher_tau` = 0 or small (user choice).
- Verification enabled.

**Shared policy:** train sub-call tokens as well as root tokens. This requires capturing sub-call trajectories as training samples.

**Pool:** mixed-domain, or a deliberate order recorded in config.

**Variants:**
- DeepSWE-style coding inside the RLM harness, with repo tools exposed as REPL helpers and tests read-only.
- OOLONG-style generated tasks.

**Eval:** held-out evals stay held out.

---

## 10. Known risks and their checks

| Risk | Check |
|---|---|
| Multi-turn drift between student and teacher | KL by turn index; gate A/B (§6.5) |
| Teacher ceiling: OPSD can at most match base + manual | Compare against the teacher-as-policy run; going beyond it is GRPO's job |
| KL concentrated on comments in code | Token-category KL report |
| Thinking mode reducing verification and backtracking, or exhausting turn budgets | Self-correction markers; `budget_hits` |
| Collapse (narrowed behavior diversity) | pass@k and entropy before handoff |
| Sub-call explosion | Batching detector; `max_subcalls` hits |
| Syntax errors | Syntax-error rate per checkpoint |
| Brittle finish (plan returned as answer, mixed FINAL forms) | `clean_finish` detector |
