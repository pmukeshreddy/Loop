# Task pipeline (AgentInstruct-style DeepSWE generation)

Run commands from `rlm-opsd/`. The pool format and acceptance rules are in
[TASKS.md](TASKS.md). Executed results are recorded in [PROGRESS.md](PROGRESS.md).

The pipeline follows AgentInstruct (Mitra et al., arXiv:2407.03502). Each
flow is implemented by a generation role whose instructions are a versioned
`SKILL.md`:

| Flow | Role | Skill | Output |
|---|---|---|---|
| Content transformation | Source analyst | [source-analysis](../skills/source-analysis/SKILL.md) | Per-repository dossier: mechanisms, defect sites, semantic sets, focused units, proposed settings |
| Seed instruction generation | Question generator | [question-generation](../skills/question-generation/SKILL.md) | Candidate specs with intended behaviors, rationale, answer kind and defect/probe/hidden-test patches |
| Refinement | Variation suggester, editor | [variation-suggester](../skills/variation-suggester/SKILL.md), [variation-editor](../skills/variation-editor/SKILL.md) | Substantive variations of accepted seeds |
| Response generation | Reference solver | [solver](../skills/solver/SKILL.md) | Reference trajectory and answer from the real RLM harness |
| Verification | Verifier | [verifier](../skills/verifier/SKILL.md) | Executable oracle programs, then an acceptance review |

## Commands

```bash
make tasks-prepare     # pin, set up, baseline, split and index (no model requests)
make tasks-generate    # resumable generation (model requests through step1.auth)
make tasks             # prepare + generate + release into an empty data/
make tasks-verify      # re-run executable verification of a released pool
make tasks-status      # counts from the work directory
```

The underlying CLI is `python -m rlm_opsd.tasks {prepare,generate,build,verify,status,reopen,repractice}`.
`generate` accepts `--repos`, `--rounds` and `--target TRAIN DEV` for pilot
batches. `--focus <behavior> ...` runs a focused top-up: seeds whose primary
behavior is outside the focus are screened out (`off_focus`), generators are
told only those behaviors are needed, and `--target` counts accepted tasks
whose family is in the focus. Tasks whose execution establishes a different
family are still released under their established behavior. `build` refuses to write into a nonempty output directory.

Model access uses the project's step-1 OAuth module (`step1.auth`, ChatGPT plan
by default; `models.auth: api-key` uses `OPENAI_API_KEY`). Sign in once with
`../.venv/bin/python -m step1.auth login` from the project root. Every completed
request is appended to `<work_dir>/usage.jsonl` with role, tokens and latency.

## Stages

1. **Prepare** (`prepare.py`). Each configured repository is shallow-cloned
   at its release tag. The pipeline checks that the tag resolves to the
   pinned commit, exports it to a clean tree, and installs it with its test
   dependencies into a dedicated uv virtualenv. The suite runs
   `stability_runs` times. Stable passing tests, consistent failures and
   flaky tests are recorded in `repos/<slug>/baseline.json`. The pipeline
   refuses any repository that is a DeepSWE-113 upstream. Repositories are
   then assigned to `train` or `dev_behavior` using a size-stratified seeded
   draw. The assignment is written once to `splits.json` and never
   recomputed. `sources.lock.json` records URL, ref, commit, license,
   tree digest, environment freeze and baseline counts. The held-out index
   holds all DeepSWE-113 instructions, with repository identities as source
   references, plus the configured partial or complete benchmark sources.
2. **Analyze.** Deterministic facts come first: modules, internal imports,
   importers, symbols, and which modules each test file imports. The source
   analyst then receives these facts and the most connected modules' text,
   and writes `repos/<slug>/dossier.json`.
3. **Generate.** Each repository runs rounds until it reaches its share of
   its split's target, or `max_rounds_per_repo`. The teacher-gate preflight
   requires every family in `dev_behavior`, so dev repositories keep
   generating within the round cap while any family is missing from the
   split. A family counts only when a reference execution establishes it.
   Each round focuses on different dossier entries and shows
   the generator the exact text of their files. The generator also receives
   the behavior and answer-kind coverage still needed for the repository,
   and questions already written there. Invalid specs are rejected with
   their validation errors.
4. **Screen.** Questions that are too long, mention RLM operations
   (`llm_query`, `FINAL`, REPL, sub-calls, and similar), or embed long code
   listings are rejected before any execution.
5. **Materialize** (`materialize.py`). The setup defect is applied to a
   fresh checkout and the full suite runs `stability_runs` times.
   Fail-to-pass tests must fail on every run and be baseline-passing. The
   defect may break at most `max_setup_fail_fraction` of passing tests and
   must not break collection. Probe patches yield the impact set, which must
   be stable, within the configured size range, and file-faithful: each
   node ID must name the context file that defines the test. Suites that
   collect through an aggregator module would otherwise produce answers the
   solver cannot derive. Hidden acceptance tests
   must fail before any fix. Defect symbols come from diffing the real files
   against AST spans, because hunk headers in generated patches are only
   approximate. The context is built from the starting state, scoped to the
   repository within the size budget or to explicit files. The real pytest
   output is appended when requested. Agent-instruction files (`AGENTS.md`,
   `CLAUDE.md`), `.github/`, lockfiles and binaries are excluded.
6. **Oracle.** For `value` tasks, and `symbols` tasks without a defect, the
   verifier writes a program that executes the repository. It never sees the
   solver's answer. The program runs twice in the sandbox and must be
   deterministic.
7. **No-repository check.** The same model answers without repository
   access. If it matches the ground truth, the task is rejected as
   answerable without the repository. Patch tasks are exempt, because a
   correct patch cannot be produced without the files. This
   cheap check runs before the reference solve.
8. **Solve** (`solver.py`). The reference solver runs through
   `rlm_opsd.harness.Episode`, the same sandboxed REPL worker, `llm_query`
   proxy, budgets and FINAL/FINAL_VAR parsing the student uses. Its system
   prompt is the OPSD teacher variant (student API plus the task-independent
   manual) followed by the solver skill. Only the first ```repl``` block of
   each message runs. A finish counts only in a message without unexecuted
   code, so every answer follows observed output. Up to `solver_attempts`
   attempts are allowed, and each one is kept. `solver_harness_overrides`
   may only relax timing limits: REPL wall time and per-sub-call timeout.
   Remote sub-calls take a median of about 12 s, against milliseconds for a
   local training server, and loops of sequential sub-calls were being
   killed by the 120 s limit. Turn, sub-call count and size, memory and CPU
   limits are always the student's. Each task's provenance records the
   overrides.
9. **Verify** (`verify.py`). Patches must apply to a fresh starting state
   without editing tests. Fail-to-pass tests (and hidden tests) must pass on
   every stability run, and no pass-to-pass test may fail on the full suite.
   Test-ID and symbol answers must equal the executable set exactly; values
   must equal the oracle output.
10. **Practice check** (`practice.py`). The reference trajectory must
    exhibit at least one intended behavior; if the intended primary is not
    exhibited, the task is released under the first exhibited one
    (`relabeled_from`). Evidence comes from runtime sub-call logs and a
    provenance analysis of the REPL code: code searches over context,
    sub-calls on selected rather than whole context, at least two successful
    sub-calls whose results reach the final answer, variables read across
    turns, and a final value that derives from `context` or sub-call results
    through code (not retyped from printed output) and was inspected before
    finishing. A direct solve must use a small context and no sub-calls.
    Only established behaviors are released, and detector tags are derived
    from them.
11. **Review and deduplicate.** The verifier reviews the verified task
    against the acceptance criteria. Accepted tasks in the same repository
    may not share a near-duplicate question or a repeated answer. A variation
    whose verified answer equals its parent's is rejected as cosmetic. Query
    overlap with held-out data is rejected.
12. **Vary.** For each accepted seed, the suggester proposes
    `variations_per_seed` changes to constraints, dependencies, failure
    conditions, evidence or deliverable. The editor implements each one as
    a full spec, which then repeats stages 4–11. Variations inherit their
    parent's repository and split.
13. **Release** (`build.py`). Accepted tasks are decontaminated against the
    held-out index (repository identity and query n-grams). Each task's
    executable ground truth is then re-run on fresh checkouts (`--runs`,
    default 1): defect and fail-to-pass sets, the reference patch, impact
    sets, defect symbols and oracles. Tasks that do not reproduce are
    rejected as `reverification_failed` and excluded, which catches
    nondeterminism that the stability runs missed. The release
    writes `manifest.jsonl`, content-addressed `contexts/`,
    `references/<task_id>/` (reference answer, patches, oracle, trajectory,
    logs, review), `build-report.json` (counts by split, family, setting,
    answer type, repository and size bucket; rejection counts by stage and
    reason; sources; skill hashes; manifest hash) and `decontamination.json`.

## Resumability, provenance and rejections

All state lives under `work_dir` (default `.deps/task-generation/`):

```text
splits.json, sources.lock.json, run.json, usage.jsonl, events.jsonl, rejections.jsonl
repos/<slug>/{baseline,facts,dossier,round-NN}.json
candidates/<cid>/{meta,spec,status,materialized,context,truth,verification,baseline,practice,review,accepted}.json
candidates/<cid>/{solve-N.json,trajectory-N.json,oracle.py,reference.patch,logs/}
```

Each stage writes its output atomically. A restart skips any stage whose
output exists, so an interrupted run resumes where it stopped. Rejected
candidates are terminal. Each rejection appears once in `rejections.jsonl`
with its stage, reason code and detail. Infrastructure errors are rejections
with code `pipeline_error` and a saved traceback in `error.json`; they are
never silently retried.

When a check itself is found to be wrong and is fixed, `reopen --codes <code>`
returns the affected candidates to pending. Only practice- and review-stage
rejections can be reopened, because their inputs (verified answer, reference
trajectory) are already stored. Each reopening is logged in `events.jsonl`.
The release report counts only final rejections. `repractice` re-derives
the behavior labels of accepted tasks from their stored reference
trajectories after the practice analysis changes. It touches only the
established behaviors, family, rationale subset and tags; answers and
verification are untouched. Each change is logged as a `repracticed` event.

## Execution isolation

Repository tests, oracle programs and patch checks run as
`sandbox-exec`-wrapped subprocesses (macOS):

- outbound network is denied, except localhost;
- file writes are confined to the checkout and a scratch directory;
- reads of credential locations (`.phase1-auth`, `~/.codex`, `~/.ssh`, and
  similar) are denied;
- the environment contains only PATH, HOME (a scratch directory), locale,
  TZ and PYTHONPATH.

Logs are rewritten so they contain no checkout, venv, interpreter or home
paths. The reference solver's REPL uses the harness's own sandboxed worker.
Reference executions raise `SandboxBackend.poll_interval_s` from 0.02 s to
0.5 s. On macOS each resource check scans the whole process table (about
10 ms), and ten concurrent episodes at 20 ms saturated the event loop. The
limits are unchanged; only how often they are checked. Training rollouts keep
the default.

Repositories that pytest itself imports (pluggy, packaging, iniconfig)
cannot be sources, because a defect in the checkout would break the runner.
Suites that only run under unittest are excluded as well.

## Configuration

All settings are in [configs/tasks.yaml](../configs/tasks.yaml):
repositories, model and per-role reasoning effort, targets, split size,
rounds, variations, concurrency, stability runs, context budgets and size
buckets, data filters, and practice-check thresholds. These are operational
and data-filter settings. They are not teacher-gate or OPSD-exit thresholds,
which remain user-owned in `gate.yaml` and `exit.yaml`.

## Loader and held-out coverage

```python
from rlm_opsd.tasks.build import load_tasks
rows = load_tasks("data/manifest.jsonl", split="train")
```

Each row is `{example_id, prompt, info}`, where `info` holds only task ID,
family, domain, tags, query and context. Train/dev release still requires
complete held-out coverage. DeepSWE-113 coverage is complete from local data.
The paper's long-context benchmarks need their reserved snapshots
(`heldout.snapshots`) before the normal loader accepts the pool. Until then,
`inspection_only=True` reads it for review. The snapshot formats and adapters
are unchanged; see `rlm_opsd/tasks/heldout.py`.
