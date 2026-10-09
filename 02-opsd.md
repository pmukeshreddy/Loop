# Step 2 — OPSD

Goal: teach one 27B model to act as the model inside the official RLM harness. It should write ```repl``` blocks, use `context`, call `llm_query` / `rlm_query`, and submit with `answer`.

This step does not try to maximize the DeepSWE solve rate. Ordering those actions so the verifier passes is step 4.

Start this step only after step 1 shows the On arm beating the Off arm.

## Algorithm

On-Policy Self-Distillation, from Zhao et al., "Self-Distilled Reasoner" (arXiv 2601.18734, code `siyan-zhao/OPSD`).

One model plays both roles by seeing different context.

- Student sees only the task `x`. It samples its own rollout `ŷ ~ p_S(· | x)`.
- Teacher sees the task plus a privileged RLM trace `y*`.
- The loss is the per-token divergence between the teacher distribution and the student distribution, taken on the student's own tokens.
- Gradients flow through the student only.

`y*` is a real RLM trajectory: the ```repl``` programs, the `llm_query` / `rlm_query` calls, the variables kept in the REPL, and the final `answer["content"]` with `answer["ready"] = True`.

The student never sees `y*` in its prompt. The teacher uses `y*` to show what a correct RLM turn looks like while scoring the student's tokens.

Freeze the teacher at the initial 27B weights and train the student with LoRA (`fixed_teacher` in the OPSD repo). That is the stable setup from that codebase. The teacher stays the same model with a richer prompt, not a second larger model.

## Where the traces come from

Run the step-1 harness (official RLM, the selected OpenAI model in the model slot) on a train-only pool of executable SWE tasks. Keep trajectories where the verifier passed, and keep a sample of well-formed failures so the student also sees recovery from a bad ```repl``` block.

Do not build this pool from the Datacurve 113, and do not reuse the 8 tasks from the step-1 comparison. Those stay eval.

The pool can be small. This stage is teaching the action format, not covering every repo. A few hundred traces is the right order of magnitude. Step 3 is the large set.

Each training row:

| Field | Who sees it |
|---|---|
| `task` | Student and teacher. The instruction, plus the RLM system prompt the official library uses. |
| `privileged_trace` | Teacher only. The stored RLM trajectory. |
| `student_rollout` | Generated during training. Not taken from native Codex logs. |

The student rollout has to be generated inside the same official RLM loop the 27B will use at inference, so the tokens it learns are ```repl``` text, not Codex tool calls.

## Checkpoint

Name the 27B checkpoint at the start of this step and write it here. It is a completion model that can be fine-tuned. It is not the OpenAI model used in phase 1. Phase 1 uses OpenAI to prove the harness and collect `y*`.

## Done when

Held-out prompts (not the Datacurve slice) show the 27B, dropped into official `RLM.completion` with its own completion backend, doing all of the following on its own:

- It emits a ```repl``` block instead of solving the task in prose.
- It reads `context` from the REPL.
- It calls `llm_query` on slices instead of printing the whole repo.
- It sets `answer["ready"] = True` only after that work.

Solve rate is allowed to stay low. That is what step 4 is for.

## Do not

- Do not put a verifier reward in this loss.
- Do not run GRPO here.
- Do not distill Codex's native edit/shell traces. Distill RLM trajectories only.
