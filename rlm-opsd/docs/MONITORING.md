# M8: OPSD monitoring and exit

M8 evaluates OPSD behavior and retention. GRPO-pool pass@k, entropy and the
mixed pass/fail readiness requirement are the M9 handoff criteria described
in SPEC §9.

`make eval-behavior` generates three runs for every fixed `dev_behavior` task:
base + short prompt (`before`), base + full manual (`teacher`), and checkpoint +
short prompt (`after`). It reports all detectors, syntax errors, sub-call
statistics, decomposition distribution, and task success by family, size bucket
and domain. Labels are used only after generation for monitoring.

The command also scores each checkpoint rollout locally: `KL(p_teacher ||
p_student)` over the full vocabulary at recorded root assistant targets. Both
distributions use the configured generation temperature. This is KL in nats,
not the training JSD and not a sampled-token logprob difference. The teacher is
the frozen initial model under the privileged prefix with LoRA bypassed; the
student has the saved adapter active. Projection is chunked at the inherited
`jsd_chunk_size`. No teacher scoring endpoint is used.

Behavior reports can run before a retention set or exit tolerances are chosen.
`make exit-check` reads a completed behavior evaluation, verifies the evidence,
generates paired base/checkpoint responses on the user-chosen retention set,
and checks exactly two conditions:

1. Every measured detector rate and `task_tag_match` rate is within the absolute
   user tolerance of teacher-as-policy, for every reported overall, family,
   size and domain group. D19 categories are compared individually. Each side
   must meet the configured `min_known` and `max_unknown_fraction`; missing or
   insufficient evidence is inconclusive, never an implicit pass.
2. The mean retention score has fallen by no more than the user tolerance from
   base to checkpoint. An improvement passes this retention condition.

Comparisons are inclusive. Only a four-binary64-ULP allowance at 1 is used for
subtraction roundoff (about 8.9e-16); this does not select a performance tolerance.
Any known failed condition makes the result failed; otherwise missing evidence
makes it inconclusive. No training or GRPO handoff happens in either command.

## Server inputs and commands

Use the pinned Linux/CUDA environment from M0 and a passed real teacher gate
with complete decontamination. The existing M2 coverage gaps and unset gate
settings remain blockers. The model backend inherits M6/M7 limits: one process,
one CUDA device, eager unsharded dense MultiLoRA, frozen base/head, no compile,
no packing/CP/FSDP. A100/H100 runtime and memory fit require validation on the
target server.

Set `configs/eval.yaml`:

| Key | Meaning |
| --- | --- |
| `training_config` | Existing OPSD TOML with exact model/revision, gate and LoRA settings; relative to eval YAML |
| `checkpoint`, `checkpoint_sha256` | Native adapter `.pt` written by the OPSD smoke, and its exact SHA-256 |
| `checkpoint_step`, `eval_interval` | Explicit step and positive evaluation interval |
| `run_label` | Human description; fixture/synthetic labels cannot authorize exit |
| `student_endpoint.base_url`, `.served_model`, `.api_key_var` | Generation endpoint serving the checkpoint; key field is an environment-variable name |
| `endpoint_checkpoint_sha256` | Operator declaration that generation uses the same adapter bytes as local scoring |
| `temperature`, `seed` | Positive sampling/scoring temperature and paired reproducible seeds |
| `review_per_family`, `kl_top_k` | Maximum readable checkpoint trajectories per family and top KL text positions |

The base and frozen-leaf generation endpoints come from the gate config.
Checkpoint generation must use a distinct endpoint/model identity from the
frozen base. The operator is responsible for serving the corresponding model
and adapter with the pinned chat template. Response aliases are checked;
remote weight/template bytes are not independently attested. Adapter publication
and the multi-step trainer are described in
[OPSD_TRAIN.md](OPSD_TRAIN.md).

Invoke `eval-behavior` from the checkpoint driver at each step. A step that is
not divisible by `eval_interval` returns `not_due` before loading a model or
creating output. At due steps, it evaluates the full fixed dev split. It does
not schedule background jobs or change the M6/M7 one-update smoke loop.

```sh
make eval-behavior-check EVAL_CONFIG=configs/eval.yaml
make eval-behavior EVAL_CONFIG=configs/eval.yaml EVAL_OUTPUT=reports/eval-step-N
```

After reviewing the teacher-gate and behavior reports, fill
`configs/exit.yaml`. The fields `retention_path`, `rules.behavior_tolerance`,
and `rules.retention_tolerance` are deliberately required and unset. Also set
`evaluation_dir`, `expected_checkpoint_sha256`, `rules.min_known` and
`rules.max_unknown_fraction`. `retention_max_tokens` controls direct retention
responses; the prompt template/thinking setting, temperature and paired seeds
come from the completed behavior run. There is no invented acceptance value.

```sh
make exit-check-check EXIT_CONFIG=configs/exit.yaml
make exit-check EXIT_CONFIG=configs/exit.yaml EXIT_OUTPUT=reports/exit-step-N
```

Retention runs use plain system/user generation, without REPL context or the
teacher manual. JSONL rows have exactly `id`, `prompt`, `answer`, `answer_type`.
The dataset is chosen by the user; no operational examples are supplied. IDs
must be unique. Answers are never sent to either endpoint.

- `exact` and `multiple_choice`: compare stripped scalar representations,
  case-sensitive. Multiple choice expects the option label alone.
- `numeric`: exact finite Decimal equality; no numeric tolerance is invented.
- `list_f1`: set F1 over stripped scalar item representations. Gold is a list of
  strings/finite numbers (or a parseable list string); responses must parse as
  lists. Duplicates/order do not matter. Partial F1 contributes to retention.

Invalid gold answers fail validation before requests. Invalid model output
scores zero. For RLM task success, malformed/no/error finishes score zero and
success means score equals one. Scoring is monitoring-only.

## Saved evidence and limits

Behavior output includes `behavior.md`, `behavior.csv`, `monitor.md`,
`divergence.csv`, `metrics.json`, `token-scores.json`, raw `rollouts/`,
`trajectories/`, request events, input hashes and `monitor.json`'s file inventory.
Readable checkpoint trajectories go to `review/step_<n>/<family>/` (up to the
requested count available for each family). Reports link to source evidence.
All root targets, including special tokens, contribute to overall and turn KL;
category means and top textual positions exclude special offsets and disclose
that count. Full decoded completions include reasoning when present.

Tokenizer offset lookup requires decoded completion IDs to round-trip exactly.
This encode operation is solely an offset check: scored sequences and the
teacher suffix always use the original rollout IDs. Missing/clipped server
records, noncanonical tokenizations, excessive aligned sequence lengths,
nonfinite scores or unsupported heads fail explicitly; no text fallback or
approximate vocabulary is used. Peak GPU memory requires measurement on the target server.

Exit verifies hashes, checkpoint identity, complete dev task/phase coverage,
request success, and freshly recomputed detector, correctness and KL summaries
before generation. It also checks current gate/prompt/data/training inputs
against behavior provenance. Hash inventories detect changed evidence; they
are not signed attestations against deliberate fabrication. Exit stores its
retention input snapshot, paired responses, request events, source hashes,
`exit.json` and `exit.md` in a new directory. Existing outputs are refused.
Failures retain partial evidence and cannot produce a passing decision.

CLI codes: completed/passed/not_due = 0, error = 1, not_run = 2, failed = 3,
inconclusive = 4. Both `--check` paths are local and send no model requests.
`exit-check` itself sends retention generation requests after validation.

Local tests use hand-derived values, actual pinned LoRA CPU tensors and
scripted HTTP responses through the real harness/client. These checks establish
CPU and protocol behavior. Checkpoint quality and retention acceptance requires
model execution with the server inputs above. See [PROGRESS.md](PROGRESS.md) for
the executed commands and logs.
