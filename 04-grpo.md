# Step 4 — GRPO

Implementation: [`rlm-opsd/docs/GRPO.md`](rlm-opsd/docs/GRPO.md), configured by
[`rlm-opsd/configs/grpo.toml`](rlm-opsd/configs/grpo.toml). The current repository
environment uses the user's October 15 +1/−1 reward convention and trains both
root and completed child branches with the same policy. Tests and GPU execution
of this implementation have not been run.

Goal: take the 27B from step 2 and train it so the RLM actions happen in an order that makes the verifier return 1.

Start only if step 1 passed and step 2 produced a 27B that already emits valid RLM turns. The tasks are the `train` split from step 3.

## Policy and environment

The policy is the 27B. It sits in the model slot of the official RLM harness. Use the trained 27B completion backend in this step.

The environment for each rollout is one synthetic instance:

1. Container at `base_commit`.
2. `RLM.completion(context, root_prompt=instruction)` with this 27B as the backend.
3. Root submission captures the shared checkout's patch against `base_commit`.
4. A fresh container runs the instance verifier.

The REPL is the official one. The model writes ```repl``` code. That code is how it reads the repo, calls `llm_query`, and builds the patch. Do not add a second agent loop.

Sub-calls (`llm_query`) run child RLMs with the same policy and their own persistent
REPL namespaces in the shared checkout. Root and completed child model tokens
are captured for training. Do not call Codex or a larger API model inside the
training loop.

## Reward

Sparse. `+1` only when all required verifier tests pass after submission; `-1`
for a submitted failing or invalid patch. Submission supports `answer["ready"]`
and the OPSD `FINAL` / `FINAL_VAR` protocol. Unsubmitted, timed-out, truncated,
and infrastructure-failed trajectories are excluded from the update and baseline.

Mask environment observations (REPL stdout, tool output) out of the policy-gradient loss. Train on the model's own tokens.

Drop a trajectory from the loss when it dies by max context, timeout, or max steps. Reward only a run that actually submitted. This is the compact filtering used in the Agentica DeepSWE training recipe. It stops the update from reinforcing a lucky patch that the model stumbled into and then wandered past.

## Update

GRPO on groups of rollouts for the same instance.

Use the Agentica GRPO++ choices that kept their SWE run stable:

- Higher clip on the positive side, so low-probability useful actions can still be reinforced.
- No KL penalty back to the step-2 weights.
- No division by the reward standard deviation.
- A constant maximum-context denominator per active native token sequence,
  averaged globally across root/child branches, rather than actual-token normalization.
- Leave-one-out advantage.
- No entropy bonus.

Roll out several completions per instance per step (the supplied config uses 8).
Uniform-reward groups contribute no advantage. The native zero-advantage filter
resamples; repeated entirely empty batches stop with an error.

Evaluate on the step-3 `dev` split every few steps, with the same verifier. The Datacurve 113 are a final report only, not a tuning set.

## Done when

On `dev`, the GRPO model passes more instances than the step-2 checkpoint under the same RLM harness, the same iteration cap, and the same verifier. Then run the Datacurve 113 once and record pass@1. Do not tune on that number.

## Do not

- Do not mix in a Codex agent at train time.
- Do not give partial credit.
- Do not train on the eval 113.
- Do not start from the base 27B and skip step 2. GRPO is here to order a behavior the model already has, not to invent the REPL format from a 0/1 reward.
