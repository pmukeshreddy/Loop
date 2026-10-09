# AGENTS.md: RLM-OPSD

## Goal

Teach a 27B model native RLM behavior with On-Policy Self-Distillation (OPSD), then hand off to GRPO for correctness.

- RLM: Recursive Language Models, Zhang, Kraska, Khattab, arXiv:2512.24601.
- OPSD: Self-Distilled Reasoner, Zhao et al., arXiv:2601.18734.

**The OPSD phase teaches behavior.** The model learns to:
- probe the context,
- search it with code,
- store results in REPL variables,
- chunk the context and call `llm_query()`,
- aggregate results in code,
- finish with `FINAL` / `FINAL_VAR`.

This phase does not optimize answer correctness.

**The GRPO phase (later) rewards correct answers.**

Read these files in order before writing code:
1. `docs/SPEC.md`
2. `docs/TASKS.md`
3. `docs/DETECTORS.md`
4. `prompts/student_system.md`
5. `prompts/teacher_manual.md`

## Stack

| Layer | Library | Role |
|---|---|---|
| RLM harness | `alexzhang13/rlm` | The paper's reference REPL and `llm_query`. Its `training/` folder exposes `rlm.RLM` as a verifiers Environment for prime-rl. |
| Environment interface | `PrimeIntellect-ai/verifiers` | The environment API that prime-rl consumes. |
| Trainer | `PrimeIntellect-ai/prime-rl` | Async rollouts, teacher inference server, on-policy distillation, LoRA, GRPO. |
| Inference | vLLM (as used by prime-rl) | Serves the student, the teacher, and sub-calls. |
| Generation and eval sweeps | Ray (optional) | Runs task generation and evaluation jobs in parallel. |

Pin exact versions or commits in `pyproject.toml` and record them in `docs/VERIFIED_APIS.md`.

## Hard rules

1. **Never fabricate results.** Every number in a report must come from an executed run and link to its log file. If something has not been run, write "not run".
2. **Verify library APIs against the pinned source before using them.** Do not guess config keys, function names, or loss formulas. Record each verified item (file path, symbol, config key) in `docs/VERIFIED_APIS.md`.
3. **Fix failures at the cause.** When a test or run fails, do not skip, xfail, or silence it, and do not weaken assertions to make it pass.
4. **No SFT stage.** The pipeline is: teacher gate → OPSD → exit check → GRPO.
5. **The long context never enters the model prompt.** It lives only in the REPL as `context`. The root model sees metadata only.
6. **y\* is task-independent.** The teacher prompt contains no answers and nothing specific to one task.
7. **Build teacher sequences from token IDs, never by re-tokenizing text.** Assert that the shared suffix is identical between the student and teacher sequences.
8. **Follow the paper's RLM design** (`docs/SPEC.md` §2). verifiers' built-in `RLMEnv` is a variant; use it only where it matches the spec.
9. **Held-out eval sets never enter training.** Decontamination is mandatory (`docs/TASKS.md` §5).
10. **Thresholds are set by the user** in `configs/gate.yaml` and `configs/exit.yaml`. Do not invent pass/fail thresholds; leave them as required config fields.

## Repo layout

```
rlm_opsd/
  harness/     # RLM env wrapper, REPL config, metadata, FINAL parsing, budgets, trajectory logging
  prompts/     # builders for x (student) and y* (teacher), token alignment
  tasks/       # generators, manifest, held-out loaders, decontamination
  detectors/   # behavior detectors, token-category KL, reports
  training/    # prime-rl configs, teacher-context hook, losses (Mode A, Mode B, gate)
  eval/        # teacher gate, three-way comparison, retention, exit check
configs/       # model.yaml, harness.yaml, tasks.yaml, gate.yaml, opsd_mode_a.toml, opsd_mode_b.toml, exit.yaml, grpo.toml
prompts/       # student_system.md, teacher_manual.md (source of truth, versioned)
docs/          # SPEC, TASKS, DETECTORS, VERIFIED_APIS, PROGRESS
tests/
```

## Milestones

Each milestone ends with passing tests and an entry in `docs/PROGRESS.md` covering what was built, what was run, and links to the logs.

| ID | Milestone | Done when |
|---|---|---|
| M0 | Setup | Dependencies pinned and installed; `VERIFIED_APIS.md` lists the harness, verifiers, and prime-rl entry points used. |
| M1 | Harness (SPEC §2) | Tests pass for metadata, stdout truncation, `FINAL`/`FINAL_VAR` parsing, turn caps, sub-call budget, sandbox limits, and trajectory schema. |
| M2 | Tasks (TASKS.md) | Generators are deterministic by seed, answers are verified on small instances, the manifest is written, and decontamination runs. |
| M3 | Prompts (SPEC §3) | x and y\* builders work; the token alignment test passes; a test confirms no answers appear in y\*. |
| M4 | Detectors (DETECTORS.md) | Every detector passes on hand-labeled fixture trajectories. |
| M5 | Teacher gate (SPEC §5) | `make teacher-gate` produces a report from real runs. |
| M6 | OPSD Mode A (SPEC §6.3) | The teacher-context hook is in place and a smoke run completes, first on a small model from the same family, then on the 27B. |
| M7 | OPSD Mode B (SPEC §6.4–6.5) | Full-vocabulary JSD loss and the optional token gate are implemented, tested, and selectable by config. |
| M8 | OPSD monitoring and exit (SPEC §7–8) | `make eval-behavior` reports behavior/KL; `make exit-check` compares student behavior to teacher-as-policy and retention to base, using real runs and user-set tolerances. No GRPO-pool readiness in M8. |
| M9 | Pre-GRPO readiness and handoff (SPEC §9) | Before any GRPO step, report GRPO-pool pass@k/entropy and check the user-set mixed pass/fail fraction. Then the GRPO config loads the OPSD checkpoint and runs a smoke step. |

## Make targets

`make test`, `make tasks`, `make teacher-gate`, `make opsd-a`, `make opsd-b`, `make eval-behavior`, `make exit-check`, `make grpo-smoke`.
