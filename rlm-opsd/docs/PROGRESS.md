# Progress

## AgentInstruct-style DeepSWE task generation (replaces synthetic M2 pool)

Date: 2026-10-10. The synthetic long-context generators, fixed query
wordings, record codecs, BANKING77 corpus, their configuration keys, tests,
and the generated pool (`data/manifest.jsonl`, `build-report.json`,
`decontamination.json`) were deleted. There is no fallback. Historical logs
under `docs/logs` and `docs/checks/task-diversity` are kept as history and
describe the removed pipeline.

The replacement ([TASKS.md](TASKS.md), [TASK_PIPELINE.md](TASK_PIPELINE.md))
organizes tasks by the RLM behavior they give practice in, with real
repository work as the setting. Roles follow AgentInstruct (arXiv:2407.03502),
each instructed by a versioned `skills/<role>/SKILL.md`: source analysis,
question generation, variation suggester, variation editor, solver and
verifier. Every answer is verified by executing the pinned repository. The
reference solver runs in the student's RLM harness, and its trajectory must
show the intended behavior. Model access uses `step1.auth`
(`gpt-6.1-sol`, ChatGPT-plan OAuth).

Sources: 20 permissive Python repositories pinned to release commits. None is
a DeepSWE-113 upstream, and `prepare` refuses those. They were split before
generation (size-stratified seeded draw): `dev_behavior` = pyparsing, attrs,
h11, toolz; `train` = the other 16
([prepare output](checks/agentinstruct-tasks/01-prepare.json),
[log](checks/agentinstruct-tasks/01-prepare.log)).

### Inspection-driven fixes

Two pilot batches and the first part of the full run were inspected,
including questions, reference trajectories and patches. Issues fixed at the
cause:

| Finding | Fix |
|---|---|
| Reference solver wrote all blocks and `FINAL_VAR` in one message, hard-coding an answer before seeing output | One REPL block per turn for reference executions; finish only in a message without unexecuted code |
| 7 of 10 pilot-1 references rebuilt the repository on disk and ran pytest/`exec` instead of investigating ([scan](checks/agentinstruct-tasks/02-pilot-1-execution-scan.txt)) | Solver skill forbids repository execution; AST detection rejects trajectories that do it (`reference_executed_repository`) |
| First execution detector was a regex and flagged a log key and a comment | AST-based detection; the affected candidates were reopened and re-evaluated |
| Ground-truth defect symbol taken from approximate hunk headers (wrong function) | Symbols from diffing the real files |
| Generator produced "what does this program print" quizzes | Long embedded listings rejected; guidance steers `value` toward real behavior questions |
| Loop-variable reassignment counted as persistent state | A variable counts only when a later block reads it before writing it |
| Strong reference read 20K+ characters per turn and never needed sub-calls | Solver follows the manual's small-window reading discipline; an unexhibited primary behavior relabels the task to the exhibited ones instead of discarding it |
| Semantically duplicate variations across parents | Suggester and reviewer see the repository's existing tasks (`duplicate_of_existing`) |
| Hidden tests edited unseen files | Hidden tests are new files |
| Event loop saturated by the sandbox watchdog's process-table scans (~10 ms each, every 20 ms per episode) | `SandboxBackend.poll_interval_s` class attribute (default unchanged); 0.5 s for reference runs |
| Variation children left spec-less by a restart caused `pipeline_error` | Resumable variations (saved suggestions, per-child edit); regression test |
| Sequential remote sub-calls killed by the 120 s REPL wall time (7 of 111 solves) | Reference-only timing overrides (wall time 900 s, sub-call timeout 180 s); structural limits unchanged |
| lark collects tests through `tests/__main__.py`, so impact IDs did not name the defining file | Impact sets must be file-faithful |
| One accepted defect made a random-replacement test fail nondeterministically | Release re-runs every task's executable ground truth and rejects non-reproducing tasks |
| Variation questions asked the solver to write regression tests, so verified patches were rejected for editing tests | Guidance forbids test authoring; deterministic `requests_test_authoring` screen |
| Practice check discarded decomposition after one transient sub-call error, and missed results written into dict items | Requires enough successful sub-calls; container writes carry provenance; `repractice` re-derived accepted labels ([output](checks/agentinstruct-tasks/07-repractice.json)) |
| `git apply --recount` swallowed the next file header in correct multi-file patches (false `reference_patch_does_not_apply`) | Exact hunk counts first, `--recount` only as fallback; stored solves re-verified without new model calls (11 reopened) |
| References retyped findings printed by sub-calls, yet `combine_verify_finish` passed because the check only saw a name on the right-hand side | Final value must derive from `context` or sub-call results through code; solver skill forbids retyping; repractice removed the label from 13 tasks ([output](checks/agentinstruct-tasks/12-repractice-evidence-provenance.json)) |
| Delegation families rare as primary (chunked_subcalls 14, recursive_decomposition 2) | Focused top-up mode (`generate --focus ...`) |
| `score_answer` (M8 monitoring) did not know the new answer types | Monitoring-only scoring for `test_ids`, `symbols` and `value`; `patch` is unknown offline and its `task_success` is omitted |

### Executed checks

| Check | Result | Evidence |
|---|---|---|
| Baselines, 3 runs per repository | 20/20 repositories with stable passing tests | [prepare log](checks/agentinstruct-tasks/01-prepare.log) |
| Pilot 1 (cachetools, click) | 4 accepted / 7 rejected under the first solver policy; archived after the execution finding | [status](checks/agentinstruct-tasks/02-pilot-1-status.json), [rejections](checks/agentinstruct-tasks/02-pilot-1-rejections.jsonl) |
| Pilot 2 (click, sqlparse, h11) | 6 accepted / 12 rejected at snapshot | [status](checks/agentinstruct-tasks/03-pilot-2-status.json), [rejections](checks/agentinstruct-tasks/03-pilot-2-rejections.jsonl) |
| Task test suites (`tests/test_task_generation.py`, `tests/test_task_release.py`, held-out adapters) | Pass, including real-repository materialization, patch verification and impact-set tests under `sandbox-exec` | `make test-m2` |
| `make test` | **571 passed, 7 failed.** All 7 failures are one test reading the historical M5 HTTP fixture, which hard-codes `/Users/mukeshreddy/Desktop/Refine deepswe/...` from the original machine; unrelated to this change | [log](checks/agentinstruct-tasks/04-make-test.log) |
| Trial release and re-verification of the first 38 accepted tasks | 37 reproduced; 1 nondeterministic defect, which motivated the release gate | `docs/checks/agentinstruct-tasks/` |

### Generation and release results

Executed 2026-10-10 to 2026-10-12 with `gpt-6.1-sol` through ChatGPT-plan
OAuth: 4,831 model calls, 38.8M input and 4.3M output tokens
([final status](checks/agentinstruct-tasks/16-final-generation-status.json),
[main run log](checks/agentinstruct-tasks/05-generate.log),
[focused top-up log](checks/agentinstruct-tasks/13-focus-topup.log)). The run
was resumed several times after the fixes above and after the Mac slept;
resumption reused stored stage outputs.

| Quantity | Count |
|---|---|
| Candidates created (seeds and variations) | 582 |
| Accepted at generation | 279 (231 train, 48 dev) |
| Final rejections | 245 (107 seed, 138 variation) |
| Left unprocessed when generation stopped | 58 |
| Release re-verification (final build) | 279 checked, 0 failed |
| Decontamination drops | 0 (DeepSWE repositories excluded up front; no query overlaps) |
| **Released to `data/`** | **279: 231 train, 48 dev_behavior; 101 are variations** |

Released by family, train/dev: inspect_locate 123/22, direct_solve 54/17,
combine_verify_finish 20/2, persistent_state 16/4, chunked_subcalls 17/2,
recursive_decomposition 1/1. Established behaviors anywhere in a task:
inspect_locate 203, combine_verify_finish 157, direct_solve 72,
persistent_state 50, chunked_subcalls 25, recursive_decomposition 8. Answer
types: patch 207, test_ids 42, value 19, symbols 11. Settings: implementation
158, change_impact 42, scattered_evidence_debugging 37, dependency_tracing 15,
test_failure_investigation 13, multi_module_fix 7, plus 4 analyst-proposed
settings (7 tasks). Context size buckets: ≤16K 73, ≤64K 3, ≤256K 46, ≤1M 115,
≤4M 42. ([build report](../data/build-report.json),
[build log](checks/agentinstruct-tasks/10-make-tasks-build.log)).

Largest rejection reasons: reference answer incorrect 57, answerable without
the repository 55, requests test authoring 26, defect breaks no tests 13,
reviewer duplicate 13, editor declined 11, practice mismatch 9, reviewer
answer leak 9, impact IDs not file-faithful 8, impact size out of range 7,
off-focus seeds 6, reviewer behavior mismatch 5, and smaller codes.

A first release built on 2026-10-11 (258 tasks) dropped one task whose
defect produced nondeterministic failures. The final release was rebuilt
after the evidence-provenance repractice and the focused top-up.

**Delegation behaviors remain rare as primary families.** A focused top-up
(`--focus chunked_subcalls recursive_decomposition`) generated 84 seeds aimed
at those behaviors. Of the 20 accepted when it was stopped, 4 kept a delegation
family and 16 established only inspect_locate: on decomposition-designed
tasks, the reference root usually made no sub-calls and read the code itself.
An experiment re-solving 8 such tasks with `gpt-6-luna` as root (sub-calls
unchanged) produced 0 sub-calls and 0 correct answers (7 exhausted 20 turns,
1 wrong) ([results](checks/agentinstruct-tasks/14-weaker-root-experiment.jsonl)),
so a weaker reference root was not adopted. Labels stay restricted to
behaviors the reference execution demonstrates. Every family is present in
`dev_behavior`, which satisfies the teacher-gate preflight grid.

Loader checks on the release: `load_tasks(..., inspection_only=True)`
returns 231 train and 48 dev rows whose `info` holds only task ID, family,
domain, tags, query and context. The normal loader refuses train/dev because
full long-context benchmark coverage is required alongside the complete
DeepSWE coverage. This release has the same partial benchmark coverage as the
previous pool. No repository
appears in both splits, and the teacher manual is byte-identical to
`manual_v1`. Representative tasks with questions, verified answers, behavior
evidence and reviewer notes are in
[11-examples.md](checks/agentinstruct-tasks/11-examples.md).

**Verification scope: task generation and release checks.** OPSD semantics are unchanged: the loader yields only
task ID, family, domain, tags, query and context; the teacher manual and
student prompt are untouched; reference trajectories are evidence only (no
SFT); and no correctness reward was added.


## Seeded task diversity (superseded 2026-10-10; pool and generators removed)

Date: 2026-10-09–10. [Task planning](../rlm_opsd/tasks/build.py) now samples each
family knob independently from the task seed using fixed values, inclusive
integer/date ranges, or explicit choices. [Configuration](../configs/tasks.yaml)
sets needles `1–8`, hops `2–4`, dense label counts `2–8`, temporal filtering
on/off, cutoffs from `2023-01-01` through `2023-06-28`, both pair relations,
repo files `8–64`, and small-control quantity records `4–24`. Dense label sets
are sampled from the full pinned corpus. Train's split multiplier is `5` and
the small-control family weight is `3`.

[Generators](../rlm_opsd/tasks/generators.py) provide four seeded wordings for
each query type. Content, label selection and wording use independent RNGs;
resolved labels, cutoff, record counts and query variant are recorded in the
manifest. The independent answer verifiers and decontamination remain in the
build path. [Usage/contracts](TASK_PIPELINE.md) and
[verified APIs](VERIFIED_APIS.md) describe the settings and replay inputs.

| Executed check | Result | Evidence |
|---|---|---|
| Regression tests before implementation | 35 failed, 50 passed; missing sampling, labels, cutoff, record counts and wording variants exposed | [red](checks/task-diversity/01-red.log) |
| Initial `make test-m2` | 94 passed, including byte-identical serial/parallel manifests | [task tests](checks/task-diversity/02-task-tests.log) |
| `make tasks` | 360 generated, independently verified and written; zero drops against the available partial held-out index | [build](checks/task-diversity/04-make-tasks.log) |
| `make tasks-verify` | All 360 saved contexts/answers verified after reload | [verification](checks/task-diversity/05-tasks-verify.log) |
| Post-build `make test-m2` | 94 passed | [task tests](checks/task-diversity/06-task-tests-final.log) |
| Pool/source audit | 300 train and 60 dev tasks; all 77 corpus labels represented in train; 284 historical log files unchanged | [audit](checks/task-diversity/07-pool-audit.json), [script](checks/task-diversity/audit_pool.py) |
| `make test` | **634 passed**, one upstream deprecation warning; M0 provenance checks also passed; exit 0 | [full suite](checks/task-diversity/08-make-test.log) |
| Documentation links, source hashes and history preservation | Passed | [artifact audit](checks/task-diversity/09-artifact-audit.json) |

The generated pool contains 72 tasks each for sparse retrieval, multi-hop,
linear aggregation and quadratic pairs, plus 36 repo QA and 36 small-context
controls. The [audit](checks/task-diversity/07-pool-audit.json) records actual
sampled distributions and query variants. The prior pool was preserved at
the [recorded backup path](checks/task-diversity/03-previous-pool.json).

The source audit found **20 normalized BANKING77 utterances shared between
the generated train/dev pools**. These upstream partitions are therefore not
disjoint at the utterance level. This is separate from reserved-benchmark
decontamination: the audit covers a partial benchmark index, and the normal
training loader requires full coverage before accepting the candidate pool ([audit](checks/task-diversity/07-pool-audit.json)).
Independent code review found no blocking issues; its minor observation about
replaying resolved dense knobs was documented: regeneration uses the original
config/TaskSpec, while manifest knobs are audit output.

**Verification scope: CPU task generation and release checks.** Evidence lives
under `docs/checks/task-diversity`; historical `docs/logs` files were preserved.

## Single-path OPSD cleanup

Date: 2026-10-09. OPSD now has one objective: exact full-vocabulary JSD with
the existing local frozen teacher. The alternate sampled-token implementation,
its configs, targets, documentation and objective-specific tests were removed.
The objective selector and sampled-loss coefficient are absent from
`OpsdConfig`; obsolete settings are rejected instead of silently ignored.

The public smoke API is now
[`training/opsd.py::OpsdTrainer`](../rlm_opsd/training/opsd.py), with
[`opsd.toml`](../configs/opsd.toml), [`opsd_small.toml`](../configs/opsd_small.toml),
`make opsd` and `make opsd-check`. Native multi-step training remains
`make opsd-train`. Its configs, transport helpers, FSDP head and reproducible
[source patch](../patches/prime-rl-opsd.patch) use the same OPSD names.
Evaluation imports/settings, SPEC, AGENTS, VERIFIED_APIS and
[OPSD usage](OPSD.md) were updated.

`frozen_teacher` and its state-restoration, no-gradient, nonfinite-adapter,
concurrency and checkpoint tests are retained. Teacher invariance after updates
is tested through `OpsdTrainer`, including the random tiny Qwen CPU graph.
Smoke evidence records the JSD objective directly; the 27B prerequisite still
requires matching real small-model evidence and its checkpoint hash.

| Executed check | Result | Evidence |
|---|---|---|
| Config regression before removal | Failed because the config reintroduced the objective selector | [red](checks/opsd-single-path/01-config-red.log) |
| First focused run | 58 passed, one teacher fixture failed because it still installed the old sampled-logprob head | [focused run](checks/opsd-single-path/02-focused.log) |
| Teacher fixture corrected to the ordinary frozen head; teacher/JSD runner tests | 21 passed | [focused green](checks/opsd-single-path/03-focused-green.log) |
| `make test` | **601 passed**, one dependency deprecation warning; exit 0, including provenance checks and CPU FSDP | [full result](checks/opsd-single-path/04-make-test.log) |
| Patch, syntax, current-name/link audit and target dry runs | Passed; all **284** historical `docs/logs` files remain byte-identical | [artifact audit](checks/opsd-single-path/05-artifact-audit.log) |

Independent review found stale remote-teacher guidance in VERIFIED_APIS; it
was replaced with the current local frozen-teacher/JSD contract. No runtime
rename or config-consumer issues were found. New execution evidence is under
`docs/checks/opsd-single-path`; historical logs and their filenames are unchanged.
**Verification scope: CPU tests, source checks and preflight validation.**

## Prime-rl OPSD multi-step integration

Date: 2026-10-09. **Implementation and CPU validation complete.** This entry
supersedes earlier statements that OPSD is limited to the one-update smoke
helper. Pretrained-model and GPU acceptance requires the server checks in
[OPSD_TRAIN.md](OPSD_TRAIN.md).

The requested integration is in prime-rl's native
`src/prime_rl/trainer/rl/train.py`, against
`09e11c7527a242b9f150c7c4c71b1b96da66cb75`. OPSD replaces the ordinary loss
inside the existing repeated optimizer loop. The native async rollout scheduler,
FSDP2 setup, checkpoint managers, and vLLM adapter synchronization remain in use.
The ignored dependency checkout is reproduced by the checked-in
[patch](../patches/prime-rl-opsd.patch) and
[before/after hash manifest](../patches/prime-rl-opsd.json).

### What changed

- [prime_step.py](../rlm_opsd/training/prime_step.py) installs a chunked JSD head
  before LoRA/FSDP wrapping. It runs the existing frozen-teacher context first,
  through the outer wrapped model, restores adapters/RNG, then runs the student
  through the same model. The existing JSD implementation supplies gradients;
  native `train.py` owns backward and optimizer/scheduler updates.
- [prime_data.py](../rlm_opsd/training/prime_data.py) carries exact rollout IDs,
  teacher IDs, and causal alignment through native transport and batch
  distribution. OPSD forbids fallback re-tokenization, packing/truncation,
  reward filters, remote teacher scoring, and SFT. Dummy ranks participate with
  zero loss; normalization uses the global assistant-token count.
- [prime_env.py](../rlm_opsd/training/prime_env.py) supplies the decontaminated
  train split and exact prefixes to verifiers. It reuses the existing RLM
  harness, metadata-only prompt, and frozen leaf endpoint.
- [prime_launch.py](../rlm_opsd/training/prime_launch.py),
  [configuration](../configs/opsd_train.toml), and `make opsd-train` launch native
  prime-rl with the patched source/config paths inherited by subprocesses.
  Preflight verifies the existing teacher gate, small-model smoke, immutable
  cached model revision, train split, and teacher-prefix headroom.
- Source provenance checks still verify unchanged installed wheels against the
  pin, while separately allowing only the complete, hash-verified source patch.
  `optimization_dtype` and `reduce_dtype` were preserved.

### Executed checks

| Check | Observed result | Evidence |
|---|---|---|
| Initial data/loss tests | Failed before implementation; passed after implementation | [red](logs/prime-mode-b/01-red.log), [green](logs/prime-mode-b/02-first-green.log) |
| Initial launcher/config tests | Failed before implementation; passed after implementation | [red](logs/prime-mode-b/03-launch-red.log), [green](logs/prime-mode-b/04-launch-green.log) |
| Native configuration round-trip | Exposed missing `run_default` path and snapshot renderer lookup; both corrected and covered in the full suite | [failure](logs/prime-mode-b/06-roundtrip-red.log), [full suite](logs/prime-mode-b/13-full-suite.log) |
| Real single-rank CPU FSDP with BF16 and activation checkpointing | Repeated nonempty/empty/nonempty updates passed | [CPU FSDP](logs/prime-mode-b/08-fsdp-cpu.log) |
| Unsupported FSDP CPU parameter offload | New rejection test failed before validator fix; passed in the full suite | [red](logs/prime-mode-b/09-offload-red.log), [full suite](logs/prime-mode-b/13-full-suite.log) |
| Original-token enforcement in native pretokenizer | Passed after adding strict OPSD flag | [green](logs/prime-mode-b/10-token-fallback-green.log) |
| Real two-rank CPU FSDP | Repeated updates matched independent dense global gradients/weights with unequal token counts and an empty rank | [two-rank check](logs/prime-mode-b/11-two-rank-cpu.log) |
| `make test` | **604 passed**, 15 deprecation warnings; provenance check passed before pytest | [full suite](logs/prime-mode-b/13-full-suite.log) |
| `make opsd-train-check` | Exit 2: required `reports/teacher-gate-manual_v1/gate.json` is absent; no model requests sent | [preflight](logs/prime-mode-b/14-launch-check.log) |
| Artifact checks | Patch hashes/idempotence, Python and shell syntax, new documentation links, whitespace checks, and `make -n opsd-train` passed | [artifact checks](logs/prime-mode-b/15-artifact-check.log) |

The first CPU FSDP attempt exposed an incorrect test fixture: its sharded toy
backbone returned a `SimpleNamespace`, outside FSDP's supported tensor pytree.
The fixture now wraps tensor-returning blocks in the same order as native
`setup_fsdp`; no production guard or assertion was weakened.
[Original failure](logs/prime-mode-b/05-fsdp-cpu.log).
Importing the native pretokenizer initially required missing Pillow; its pinned
upstream-lock version and msgspec are now in `requirements-m6-local.txt`.
[Import failure](logs/prime-mode-b/07-token-fallback-red.log).
The original provenance checker rejected the intentional patch; it now verifies
the overlay separately from original installed bytes.
[Original failure](logs/prime-mode-b/12-provenance-red.log).

An independent code review identified the renderer round-trip, upstream token
fallback, unsupported CPU offload, and per-microbatch JSD logging issues. These
were corrected before the full suite. Patch reconstruction/idempotence, source
drift rejection, native config validation, causal alignment, dense-reference
JSD/gradients, optional token gating, activation checkpointing, and frozen
teacher invariance are covered by the new tests.

**Server acceptance requirements:** GPU/CUDA/NCCL training, vLLM rollout and
weight synchronization, pretrained small-model and 27B updates, checkpoint/resume,
and memory/throughput measurements. Gate thresholds are operator inputs. See
[OPSD_TRAIN.md](OPSD_TRAIN.md) for commands and prerequisites; the evidence above
covers CPU integration.

## M0 — pinned dependencies and server installer

Date: 2026-10-09 UTC. Scope: M0 only.

**Verification scope:** Dependencies are pinned, the local inspection environment is installed, and API/source smoke checks pass. Full prime-rl installation failed on this Apple Silicon Mac because its GPU dependencies target Linux/CUDA. The supplied server installer performs runtime installation and acceptance checks on an H100/A100-class host; the local evidence covers dependency resolution and source/API checks.

### Inputs read

Read `AGENTS.md`, then `SPEC.md`, `TASKS.md`, `DETECTORS.md`, `student_system.md`, and `teacher_manual.md`, in that order. The supplied files are at the project root, whereas AGENTS.md describes `docs/` and `prompts/` paths. The original files were preserved. Their SHA-256 hashes are recorded in the [source catalog](logs/m0/23-source-catalog.log).

Initial read-only commands included `pwd`, `rg --files`, `cat AGENTS.md`, `cat SPEC.md TASKS.md DETECTORS.md student_system.md teacher_manual.md`, `git rev-parse --show-toplevel`, and `git status --short --branch`. The containing Git repository is the parent `Refine deepswe` project; `rlm-opsd/` was untracked input. All deliverables and dependency environments were kept inside `rlm-opsd/`; no commit or push was made. Workflow planning, debugging, and verification guidance was consulted; the user's M0-only boundary governs the work.

### Deliverables

- [pyproject.toml](../pyproject.toml): immutable RLM, training-adapter, verifiers, prime-rl, and config-package pins; supporting source overrides.
- [.python-version](../.python-version): Python 3.12.12, matching prime-rl's Python 3.12 requirement.
- [VERIFIED_APIS.md](VERIFIED_APIS.md): exact source paths, public symbols, configuration keys, teacher-request location, native loss formula, and deviations from SPEC.
- [requirements-m0-local.in](../requirements-m0-local.in), [local lock](../requirements-m0-local.lock), [overrides](../requirements-m0-overrides.txt): the reproducible macOS inspection dependency set. These do not claim GPU-runtime readiness.
- [server additions lock](../requirements-m0-server-additions.lock): RLM/verifiers dependencies resolved for Linux x86_64, constrained to shared versions in pinned prime-rl's runtime lock. The server installer uses upstream's own frozen lock for CUDA/trainer dependencies.
- [scripts/check_m0.py](../scripts/check_m0.py): offline imports/configuration, installed-source provenance and byte comparisons, and an actual upstream subprocess REPL smoke check. These are installation checks, not the M1 harness suite.
- [scripts/setup_m0_server.sh](../scripts/setup_m0_server.sh): Linux x86_64 H100/A100 setup, separate `.venv-server`, frozen upstream runtime, pinned additions, dependency/import/CUDA checks, timestamped logs. No model download, SFT, rollout, or training invocation.
- [Makefile](../Makefile): M0 targets `make test`, `make check-deps`, `make setup-server`.

### What ran and what happened

The logs retain failures as well as successes. Most command groups use shell tracing and `tee`, with `pipefail`; installation/verification groups use `set -e`. Exploratory search logs can contain missing-path diagnostics and are not passing installation checks.

| Commands / activity | Observed result | Log |
|---|---|---|
| `date -u`, `uname -sm`, `uv --version`, `python3 --version`, `git status`, `docker info` | Darwin arm64; system Python 3.13.5; uv 0.9.26; Docker daemon unavailable | [00 host](logs/m0/00-host.log) |
| `git clone --depth 1` for the three upstream repositories | Clones created in `.deps/` | [01 clones](logs/m0/01-clone.log) |
| `git rev-parse HEAD`, `cat` upstream project metadata | Initial moving-branch commits/requirements recorded; these were candidates, not all final pins | [02 metadata](logs/m0/02-upstream-metadata.log) |
| `rg`, `cat`, `git ls-tree`, `git log` | Current API incompatibility identified | [03 discovery](logs/m0/03-api-discovery.log) |
| `git fetch --unshallow --tags`, history searches for `teacher_tau` | Located the change that replaced the required loss schema | [04 prime history](logs/m0/04-prime-history.log) |
| RLM history fetch/search for adapter and finish protocol | Training adapter was introduced after answer-dictionary protocol change | [05 RLM history](logs/m0/05-rlm-history.log) |
| `git show eaf95997^:pyproject.toml`, `git rev-parse`, lock/config inspection | Selected prime-rl `09e11c...`; one exploratory config path was absent because configs are a separate subpackage | [06 selection](logs/m0/06-pin-candidate.log) |
| Checkout prime-rl, fetch/checkout its verifiers pin; `uv venv --python 3.12 .venv` | Exact checkouts and Python 3.12.12 local environment created | [07 pins/environment](logs/m0/07-selected-pins.log) |
| Prime config/teacher/loss searches and source reads | Teacher helper located in `orchestrator/utils.py`; guessed `teacher.py` does not exist | [08 prime source](logs/m0/08-prime-source.log) |
| `uv pip install --python .venv/bin/python -r pyproject.toml` with initial Git URLs | Failed: automatic recursive Git fetch tried upstream private/SSH submodules | [09 Git install failure](logs/m0/09-full-install.log) |
| RLM constructors/parsing/backend source reads | Inference and training interfaces recorded | [10 RLM source](logs/m0/10-rlm-source.log) |
| Same full install using exact-commit prime-rl archives | Failed: vLLM dependency wheels unavailable for macOS arm64 | [11 platform blocker](logs/m0/11-full-install-archive.log) |
| verifiers environment and training-adapter source reads | Loader, lifecycle, scoring, state/token interfaces recorded | [12 environment source](logs/m0/12-environment-source.log) |
| `uv pip compile --exclude-newer 2026-05-28` for RLM/adapter/verifiers; install resulting lock | Core dependencies installed. Temporary core lock subsequently superseded by the checked-in local lock | [13 core install](logs/m0/13-core-install.log) |
| Prompt builder, worker, proxy, and environment-loader source reads | Protocol/prompt/sandbox differences recorded; no implementation changes | [14 protocol](logs/m0/14-protocol-source.log) |
| Compile/install local config dependency set; `uv pip check` before expansion | Core check passed; config wheel build failed because uv traversed absent archive workspace members | [15 config install](logs/m0/15-local-config-install.log) |
| Import `rlm`, `rlm_train`, `verifiers`; assert adapter subclass | Passed | [16 imports](logs/m0/16-core-imports.log) |
| Retry config build with `uv pip install --no-sources` | Same missing-workspace-member build failure; flag did not fix it | [17 failed flag](logs/m0/17-local-install-no-sources.log) |
| Install pip 25.3; `pip install --no-deps -r requirements-m0-local.lock`; `uv pip check` | pip built the archive correctly; check exposed renderers archive's `0.0.0` fallback version | [18 build/version finding](logs/m0/18-local-install-pip.log) |
| Pin renderers via Git at the same commit; regenerate local lock; pip install; dependency check | VCS metadata restored renderers `0.1.8.dev4`; **all local inspection dependencies compatible** before adding the prime-rl source wheel | [19 corrected local install](logs/m0/19-local-install-vcs-version.log) |
| `pip install --no-deps` pinned prime-rl archive; `make test` | Source wheel installed; 3 offline smoke tests passed, with installed Python bytes matching all five pinned distributions | [20 source install/smoke](logs/m0/20-prime-source-and-smoke.log) |
| `make check-deps` after prime-rl source install | Failed: 18 missing runtime dependencies; intentionally reported, not suppressed | [21 full dependency check](logs/m0/21-final-dependency-check.log) |
| `.venv/bin/rl --help` | Failed at import: missing `pynvml`; execution stopped before CLI startup | [22 CLI](logs/m0/22-cli-check.log) |
| AST symbol/signature catalog, file/input hashes, metadata provenance | Exact audited paths and symbols recorded | [23 catalog](logs/m0/23-source-catalog.log) |
| Public server submodule reachability; `uvx --from uv==0.11.1 uv --version` | Public repository accessible; selected uv version executed | [24 prerequisites](logs/m0/24-server-prerequisites.log) |
| Initialize public workspace submodules with command-scoped HTTPS rewrite; `uv export --frozen --no-dev --extra flash-attn` | Pinned upstream runtime lock exported successfully; no CUDA packages installed | [25 frozen export](logs/m0/25-server-lock-export.log) |
| Extract shared upstream versions; `uv pip compile --python-version 3.12 --python-platform x86_64-manylinux_2_34 ...`; `bash -n` | Linux additions resolved against 102 common upstream constraints; shell syntax passed | [26 Linux resolution](logs/m0/26-server-additions-check.log) |
| `bash -n`, execute installer on Mac and assert rejection, `make test` | Syntax passed; unsupported host rejected with exit 2 before installation; 3 local smoke tests passed | [27 final local checks](logs/m0/27-final-local-checks.log) |
| Compare primary pins across manifests/locks, check local documentation links, parse Python, inspect M0 scope, `git diff --check` | Pin/link/syntax/scope checks passed. Git whitespace check ran; project files remain untracked in the parent repository | [28 artifact review](logs/m0/28-artifact-review.log) |

### Reproduce local inspection

Run from `rlm-opsd/`. A clean machine also needs the `.deps` checkouts at the commits in VERIFIED_APIS.md for source-byte comparison; clone without recursive submodules and check out each exact commit. The server script automates this for its supported platform.

```bash
uv venv --python 3.12.12 .venv
uv pip install --python .venv/bin/python 'pip==25.3'
.venv/bin/python -m pip install --no-deps -r requirements-m0-local.lock
uv pip check --python .venv/bin/python
.venv/bin/python -m pip install --no-deps \
  'prime-rl @ https://github.com/PrimeIntellect-ai/prime-rl/archive/09e11c7527a242b9f150c7c4c71b1b96da66cb75.tar.gz'
make test
make check-deps
```

The first `--no-deps` installs an already resolved complete **inspection** lock; its closure was checked successfully. The second deliberately installs only the trainer's source wheel. Consequently, the final `make check-deps` fails on this Mac and is **not** an expected success criterion for the inspection subset. No dependency failure is hidden by the smoke suite.

### GPU server installation

Target: Linux x86_64, glibc compatible with the pinned `manylinux_2_34` vLLM wheel, an A100/H100-class NVIDIA GPU, and a driver compatible with the pinned CUDA artifacts. `git`, `uvx`, and `nvidia-smi` must be available. CUDA extension builds may require the matching CUDA development toolchain. The installation uses upstream's locked torch/vLLM/FlashAttention versions rather than unpinned latest packages.

```bash
cd rlm-opsd
make setup-server
```

The script installs into `.venv-server`, retains the upstream runtime versions while adding the checked-in RLM lock, verifies the pinned installed sources, runs `rl --help`, and checks CUDA/FlashAttention/vLLM imports. It writes `docs/logs/m0-server/<UTC timestamp>/setup.log`, source/requirement records, runtime constraints, and final installed packages. It exits on any failure. It does not start training or choose model/harness/gate settings. Invoke the server interpreter directly afterward; an unrelated `uv sync` could replace the deliberately combined environment.

**Verification scope:** M0 evidence covers local source imports, the subprocess REPL, frozen lock export and cross-platform dependency resolution. Linux/CUDA runtime acceptance requires the server installer and its import/kernel checks. Model inference, numerical training checks and evaluations have separate execution requirements.

### Integration decisions

The latest upstream APIs do not match this spec, so historical prime-rl/verifiers pins preserve the required adapter/loss surface. M0 inspected the native teacher-scoring and loss interfaces. The project-specific finish protocol, metadata, prompts, frozen subcalls and budgets are described under M1–M3; the frozen-teacher and JSD integration is described under M6–M7 and the native multi-step section above. Server installation uses the dedicated Linux/CUDA path.
## M1 — harness complete

Date: 2026-10-09. Scope: SPEC §2 only, following the user's authorization to
implement M1 and stop. **Status: complete.** The final `make test` passed all
3 M0 source/API smoke checks and 31 M1 tests; shell syntax and Python compilation
also passed. See the [final executed log](logs/m1/13-final-tests.log). One
upstream `importlib.abc.Traversable` deprecation warning remains visible; no test
was skipped, marked xfail, or weakened to obtain a pass.

### Inputs and scope

Read `AGENTS.md` and every listed input before implementation: the supplied root
`SPEC.md`, `TASKS.md`, `DETECTORS.md`, `student_system.md`, `teacher_manual.md`.
The canonical `docs/` and `prompts/` paths now link to those originals, with byte
equality and hashes checked in [09](logs/m1/09-layout-and-install.log). The
original content and M0 dependency pins were preserved. No worktree, commit,
push, model download, or external model request was made.

The user's M1-only request and existing specification supplied the implementation
scope. Test-driven development, debugging, and verification guidance were used;
the [implementation plan](superpowers/plans/2026-10-09-m1.md) records the design.
Initial read-only inspection used `pwd`, `rg --files`, `cat`/`sed` on the guidance,
source and manifests, `git status`, and `rg` for pinned symbols. A guessed
`verifiers/utils/decorators.py` path did not exist; the actual file is
`verifiers/decorators.py`, captured in the source catalog below.

### Built

- [rlm_opsd/harness](../rlm_opsd/harness): a reference-adapter subclass and real
  subprocess REPL; metadata-only initialization; persistent variables/function
  globals; code extraction; bounded combined stdout/stderr with full-length
  notices and tracebacks; external `FINAL`/`FINAL_VAR`; missing-variable recovery
  and ignored-suffix logging.
- [configs/harness.yaml](../configs/harness.yaml): root token/turn budgets,
  subcall count/size/concurrency/timeouts, recursion opt-in/depth, output and
  wall/memory/CPU limits. Operational defaults are adjustable; no gate or exit
  thresholds were invented.
- Frozen-model subcalls through the pinned localhost proxy and verifiers client,
  with request logging, no root-client fallback, shared concurrency/count budgets,
  and optional child REPL recursion. Local HTTP tests exercise the actual client
  wire serialization; the server's actual frozen weights are an operator setup
  requirement, not something a local test can establish.
- Atomic JSON trajectories on success, caps, errors, and cancellation. Full
  provider completion IDs are copied unchanged, even when verifiers clips its
  separate training token representation. Provider reasoning fields remain in
  the next root request. Token alignment is described under M3.
- [Tests](../tests/test_harness.py), [verifiers/HTTP integration](../tests/test_verifiers_env.py),
  and [server manifest regression](../tests/test_setup_manifest.py). Tests use
  deterministic model transports and actual workers, not a simulated REPL.
- [HARNESS.md](HARNESS.md) for usage, inputs, lifecycle and limitations;
  [VERIFIED_APIS.md](VERIFIED_APIS.md) for new exact source interfaces;
  [third-party notice](../THIRD_PARTY_NOTICES.md) for the adapted RLM code.
- [requirements-m1.txt](../requirements-m1.txt) and explicit support pins in
  `pyproject.toml`; server setup installs them under its runtime constraints.
  M0 provenance checks now also verify exact-version support packages while
  retaining every original source-byte assertion. `make test` runs both suites;
  `make test-m1` runs the harness suite alone.

### Commands and outcomes

Commands ran from `rlm-opsd/` with `.venv/bin/python`. Failed runs were retained.
The test sources were written before the initial red run and implementation;
additional regressions were run failing before their corresponding fixes.

| Commands / activity | Observed result | Log |
|---|---|---|
| Read pinned runtime versions via `tomllib`; `make test` before M1 | M0's 3 checks passed; selected support versions match the pinned server lock | [00 baseline](logs/m1/00-baseline.log) |
| `python -m pytest tests -q --tb=short`, before implementation | 19 tests failed because `rlm_opsd` did not exist | [01 red contracts](logs/m1/01-red-contracts.log) |
| `uv pip install --python .venv/bin/python psutil==7.2.2`; inspect installed method signatures | Installed exact support dependency; verified resource-monitoring interface | [02 dependency](logs/m1/02-resource-dependency.log) |
| Same pytest command after initial implementation | 17 passed, 2 failed: fixture responses omitted required pinned verifiers fields | [03 implementation](logs/m1/03-first-implementation.log) |
| Correct fixtures to construct valid `Response`/`ResponseMessage`; rerun pytest | 19 passed; assertions unchanged | [04 fixture correction](logs/m1/04-correct-response-fixtures.log) |
| Add timeout, recursion/depth, persistent function globals/deletion, child cleanup, parser and real HTTP loader cases; run pytest | 28 passed, 1 failed: frozen-client config dict was not resolved into a client | [05 expanded contracts](logs/m1/05-expanded-contracts.log) |
| Resolve client config through pinned API; `pytest tests/test_verifiers_env.py` | HTTP subcall succeeded; remaining assertion exposed dropped reasoning in next root request | [06 HTTP integration](logs/m1/06-http-client-integration.log) |
| Preserve original message fields; run full pytest suite | 29 passed | [07 contracts](logs/m1/07-complete-contracts.log) |
| Add raw-token regression with `max_seq_len` clipping; run integration tests | Regression failed: JSON had clipped training IDs instead of full provider IDs | [08 token regression](logs/m1/08-raw-token-regression.log) |
| Create canonical input symlinks, assert byte equality, hash inputs; install `requirements-m1.txt`; `bash -n` | Links/versions/shell syntax verified | [09 layout/install](logs/m1/09-layout-and-install.log) |
| Copy IDs directly from `response.message.tokens`; rerun integration tests | 3 integration cases passed, including clipped training representation | [10 token fix](logs/m1/10-original-token-ids.log) |
| AST/signature and SHA-256 catalog of pinned source and installed support APIs; package-version inspection | Exact paths, signatures and installed versions recorded | [11 source catalog](logs/m1/11-api-source-catalog.log) |
| Run M0 checks and new server-manifest export regression after adding version pins | Both exposed the old assumption that every dependency was a source URL | [12 manifest regression](logs/m1/12-manifest-regression.log) |
| Support exact-version requirements without removing source checks; `make test`; `bash -n scripts/setup_m0_server.sh`; `python -m compileall -q rlm_opsd tests scripts/check_m0.py` | All 3 M0 checks and 31 M1 tests passed; shell/Python checks passed | [13 final tests](logs/m1/13-final-tests.log) |
| Documentation-link, whitespace, scope, original-input and artifact-hash review; `git diff --check` / `git status` | Final local artifact review (project remains untracked in parent repository) | [14 artifact review](logs/m1/14-artifact-review.log) |

### Verification boundary

Local tests exercised actual wall-time, cumulative CPU and resident-memory
termination, child-process cleanup, last-turn execution, metadata/prefix privacy,
stdout/stderr/truncation, finish parsing, subcall limits/concurrency/timeouts,
recursion/depth, cancellation, and serialized schema/IDs. The process-group and
sampled resource watchdogs are **resource containment, not a hostile-code security
sandbox**; full semantics and sampling limitations are in HARNESS.md.

**Server requirements:** Linux address-space enforcement, CUDA imports/kernels,
A100/H100 inference, training and teacher evaluation require their corresponding
server checks. The local evidence covers the harness and macOS watchdog; the
M0 dependency failures document the boundary of this inspection environment.

## M2 — task generation and partial held-out coverage (superseded 2026-10-10 by the AgentInstruct-style pipeline)

Date: 2026-10-09. Scope: M2 / TASKS.md only. The milestone's code and local
acceptance checks are complete: deterministic generators, independent answer
verifiers, a materialized manifest, and an executed decontamination pass. The
pass covers only the public query artifact actually imported. **The generated
pool is inspection-only until complete reserved benchmark queries and source
documents are imported and decontamination reruns.** The normal train/dev loader
rejects this pool rather than claiming full coverage.

The [full suite](logs/m2/14-full-suite.log) passed 3 M0 smoke checks and 92 pytest
tests (31 M1 + 61 M2); Python compilation passed. The existing upstream
`importlib.abc.Traversable` deprecation warning remains visible. The
[generation run](logs/m2/12-generation-and-decontamination.log) wrote and
independently reverified 112 tasks. These are generator/oracle results, not model
accuracy results.

### Inputs and implementation

Read AGENTS.md and its listed documents in order, using the canonical docs and
prompt links. Original input hashes were rechecked in the
[pool audit](logs/m2/13-materialized-pool-audit.log). The user confirmed there are
no local reserved benchmark snapshots/indexes. Public source discovery located
and pinned classification data and benchmark schemas; only the explicitly
listed artifacts were downloaded. No substitute dataset was silently used for
a missing benchmark.

The user's specification and M2-only authorization define the scope. Planning,
test-driven development, debugging and verification guidance were used; the
[implementation plan](superpowers/plans/2026-10-09-m2.md) records the sequence.
The initial tests ran failing before implementation. Added regression tests also
ran failing before their corresponding fixes. No tests were skipped, marked
xfail, or weakened to get a passing result.

- [rlm_opsd/tasks](../rlm_opsd/tasks): all six deterministic task families,
  lossless encodings, source provenance, offline independent verifiers, real
  process-pool generation, atomic manifest/context writes, explicit split
  loading and answer-free OPSD records.
- [configs/tasks.yaml](../configs/tasks.yaml): source URLs/revisions/SHA-256,
  family weights, sizes, structures, split counts, seed and data-filter settings.
  No new library dependencies or changes to M0/M1 dependency pins.
- Strict JSON/JSONL held-out adapters for S-NIAH, BrowseComp-Plus 1K docs,
  OOLONG `trec_coarse`, OOLONG-Pairs, and LongBench-v2 CodeQA. These return only
  `eval_heldout` tasks. Adapter verification uses small labelled fixtures;
  full coverage requires the reserved benchmark exports.
- Decontamination by normalized exact/near query and shared source identity or
  content; per-rule/per-split reporting; missing coverage, manifest changes,
  context corruption, duplicate IDs and path escape guards.
- [Task tests](../tests/test_tasks.py), [pipeline tests](../tests/test_task_pipeline.py),
  [held-out tests](../tests/test_heldout_tasks.py), and [CLI tests](../tests/test_task_cli.py).
  Serial/parallel manifests are compared byte-for-byte; known-answer fixtures
  exercise every oracle and all decontamination rules, including both splits.
- [TASK_PIPELINE.md](TASK_PIPELINE.md) documents reproduction, configuration,
  data shapes, required reserved exports and coverage limits.
  [VERIFIED_APIS.md](VERIFIED_APIS.md) records exact entry points and inspected
  schemas. [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) attributes BANKING77.
- `make test-m2`, `make tasks`, `make tasks-prepare`, and `make tasks-verify`.
  `make test-m1` now explicitly selects its original harness files;
  `make test` runs all milestones' tests. Generated context files are ignored
  by Git; the manifest and reports are retained.

### Commands and observed outcomes

Commands ran from `rlm-opsd/` with `.venv/bin/python`. Logs preserve red runs and
failures. Exploratory reads included `rg`, `cat`/`sed`, `git status`, primary
source/schema browsing, and GitHub/Hugging Face metadata requests. Shell command
groups used tracing and `pipefail`; successful build/check groups used `set -e`.

| Commands / activity | Observed result | Log |
|---|---|---|
| `make test` before M2 | 3 M0 checks and 31 M1 tests passed | [00 baseline](logs/m2/00-baseline.log) |
| Python `urllib` requests to primary GitHub/HF metadata | Exact candidate dataset revisions and schema/file listings captured | [01 discovery](logs/m2/01-public-source-discovery.log) |
| Download exact-revision BANKING77 CSVs/license, OOLONG-Pairs templates, BrowseComp/LongBench READMEs; compute SHA-256 | Public files pinned and cached; sizes/hashes logged | [02 source snapshots](logs/m2/02-source-snapshots.log) |
| `pytest tests/test_tasks.py tests/test_task_pipeline.py tests/test_heldout_tasks.py -q --tb=short` before implementation | 54 failures: task package absent | [03 red contracts](logs/m2/03-red-contracts.log) |
| `pytest tests/test_tasks.py -q --tb=short` after generator/oracle implementation | 45 passed | [04 generators](logs/m2/04-generators.log) |
| Import actual BANKING77 CSV with default ambiguity rejection | Failed on conflicting normalized-text labels, exposing real source ambiguity | [05 import finding](logs/m2/05-classification-import.log) |
| `pytest tests/test_heldout_tasks.py tests/test_task_pipeline.py -q --tb=short` | 7 passed, 2 failed because build module was still absent | [06 partial implementation](logs/m2/06-heldout-and-decontam.log) |
| Add ambiguous-source regression; `pytest tests/test_tasks.py -k banking -q --tb=short` | Failed before explicit drop-policy support existed | [07 red ambiguity](logs/m2/07-ambiguous-source-red.log) |
| Implement audited ambiguity policy and build pipeline; run the three initial test files | 55 passed, including actual subprocess parallelism | [08 pipeline](logs/m2/08-pipeline-implementation.log) |
| Write CLI/config tests; `pytest tests/test_task_cli.py -q --tb=short` | 2 failed, 1 passed; missing CLI and config | [09 CLI red](logs/m2/09-cli-red.log) |
| Implement CLI/config; run all four M2 test files | 58 passed | [10 CLI green](logs/m2/10-cli-and-pipeline.log) |
| Add JSON/JSONL importer and release-guard regressions; run held-out/pipeline files | 1 failed, 11 passed; snapshot loader absent | [11 importer red](logs/m2/11-importer-and-release-red.log) |
| Implement importer; `make test-m2`; `make tasks`; `make tasks-verify` | 61 passed; 112 generated, verified and written; all 112 reverified from disk; partial query decontamination ran | [12 real pool](logs/m2/12-generation-and-decontamination.log) |
| Audit manifest grid/counts/source partitions; exercise normal training loader; hash input/artifacts | Actual counts below; loader rejects incomplete coverage; original inputs preserved | [13 pool audit](logs/m2/13-materialized-pool-audit.log) |
| `make test`; `python -m compileall -q rlm_opsd tests` | 3 M0 checks and 92 pytest tests passed; compilation passed | [14 full suite](logs/m2/14-full-suite.log) |
| Pin/read RULER schema source and OOLONG cards; AST signature/file hash catalog | Exact inspected source revisions, paths, fields and local entry points recorded | [15 source catalog](logs/m2/15-source-catalog.log) |
| Check local doc links, whitespace, scope, source overlap, artifact hashes and Git state | Final artifact review, with results retained | [16 artifact review](logs/m2/16-artifact-review.log) |

### Actual pool and eligible grid

Source: [materialized pool audit](logs/m2/13-materialized-pool-audit.log),
[manifest](../data/manifest.jsonl), and [build report](../data/build-report.json).
The two splits have identical eligible-cell counts and distinct derived seeds.
Each table row below gives **counts per split**, for both `train` and
`dev_behavior`; `str/list` is shown within each cell.

| Family | 8,192 chars | 32,768 | 131,072 | 524,288 | 2,097,152 | 8,388,608 | Total per split |
|---|---|---|---|---|---|---|---|
| sparse_retrieval | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 12 |
| multi_hop | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 12 |
| linear_aggregation | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 12 |
| quadratic_pairs | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 12 |
| repo_qa | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 | 6 |
| small_context_control | 1/1 | excluded | excluded | excluded | excluded | excluded | 2 |

Total: **56 train + 56 dev = 112 tasks**, **217,042,469 actual context chars**.
Structures: 50 string and 62 list contexts. Encodings: 21 plain, 21 JSONL,
19 CSV, 19 logs and 32 Markdown. Repo QA's file-list semantics exclude string
cells; small controls exclude buckets at or above the configured direct-read
limit. These exclusions are recorded explicitly in the build report. All other
eligible family/bucket/structure cells are represented. No eval benchmark was
inserted into either generated split. [Count evidence](logs/m2/13-materialized-pool-audit.log).

BANKING77 source import counts, from the [executed source preparation](logs/m2/12-generation-and-decontamination.log):

| Upstream partition → project split | Raw rows | Ambiguous rows removed | Duplicate rows removed | Retained |
|---|---|---|---|---|
| train → train | 10,003 | 2 | 30 | 9,971 |
| test → dev_behavior | 3,080 | 2 | 3 | 3,075 |

The full upstream train/test partitions share 25 normalized utterances
([audit](logs/m2/13-materialized-pool-audit.log)). The configured selected-label
pool actually materialized here shares **zero** source content hashes between
its train/dev tasks ([final artifact audit](logs/m2/16-artifact-review.log)).
This result applies to this pool; broader future label selections must recheck
train/dev source overlap. Neither partition uses TREC.

### Decontamination result and verification boundary

The actual held-out index contains 20 public OOLONG-Pairs question templates.
The [decontamination report](../data/decontamination.json) records 112 inputs,
112 retained, and 0 dropped by each of `exact_query`, `near_query`,
`shared_source`, and `shared_content`.
[Executed evidence](logs/m2/12-generation-and-decontamination.log).

**Those source-overlap zeros do not certify source disjointness:** the downloaded
template artifact contains no benchmark source contexts. Full query/source
coverage is missing for all five named benchmark sets, including full
OOLONG-Pairs contexts. Accordingly, `coverage_complete=false`, all missing
benchmarks are named in the report, and normal train/dev loading fails with
`heldout coverage is incomplete; pool is inspection-only`. Positive coverage
and drop-rule behavior were tested with explicit fixtures, not fabricated full
benchmark data. Complete reserved exports and a fresh decontamination build are
required before using this pool for training or teacher-gate evaluation.

**Verification scope:** deterministic generators, independent answer verifiers,
fixture adapters and decontamination against the imported public templates.
Full benchmark certification requires the reserved exports and a fresh build;
model evaluation, teacher gate and training require the configured server.
Prompt, detector and training implementation evidence appears in the corresponding
sections below.

## M3 — prompts complete

Date: 2026-10-09. Scope: SPEC §3 only. **Status: complete.** Student/teacher
builders, pinned chat prefixes, token-ID suffix alignment, manual versioning and
harness integration are implemented. The final run passed **3 M0 smoke checks
and 120 pytest tests**, including **28 new M3 cases**, plus Python compilation
and real-tokenizer checks in both thinking modes.
[Final executed log](logs/m3/09-final-tests.log).

### Inputs, decisions and scope

Read AGENTS.md and every listed source in order: SPEC, TASKS, DETECTORS, student
system and teacher manual. Canonical source links and original bytes are
preserved. The user selected **Qwen/Qwen3.5-27B** after the model question.
Its tokenizer/template revision is
`fc05daec18b0a78c049392ed2e771dde82bdf654`; exact artifact checksums and download
URLs are recorded in [01](logs/m3/01-tokenizer-source.log) and
[VERIFIED_APIS.md](VERIFIED_APIS.md). No model weights were downloaded.

The existing specification supplied the design and the user authorized its
execution. Planning, test-driven development, debugging, verification and a
separate read-only code review were used. The
[implementation plan](superpowers/plans/2026-10-09-m3.md) records scope and test
focus. Work stayed in the shared project, which remains untracked in the parent
repository; no branch, commit, push or external publication was made.

Thinking is explicitly enabled by default for both prefixes, with one shared
configurable Boolean. The real-tokenizer smoke also exercises disabled thinking.
The teacher's privileged manual addition depends only on operating limits. The
shared API block still contains permitted metadata, and both user messages hold
the identical query, as SPEC §3 defines. There is no task answer input to the
builder; fixed illustrative code/query text from the supplied manual is retained.

### Built

- [rlm_opsd/prompts](../rlm_opsd/prompts): one-pass named-placeholder rendering,
  checksum-verified prompt sources, exact x/y* message builders, one pinned chat
  renderer, and `build_teacher_sequence` with exact prefix validation and suffix
  equality assertion. The suffix helper has no tokenizer dependency.
- [configs/prompts.yaml](../configs/prompts.yaml): exact model revision,
  template/tokenizer/config hashes and thinking setting. The unmodified chat
  template is [vendored](../prompts/chat_template.jinja), with its
  [source license](../prompts/QWEN_LICENSE). Tokenizer JSONs are ignored local
  cache artifacts. No new library dependency or M0 pin change.
- [Version registry](../prompts/versions.json), immutable
  [manual_v1](../prompts/versions/manual_v1.md) snapshot, and
  [manual changelog](../prompts/CHANGELOG.md). Unregistered versions, altered
  source bytes and task-metadata placeholders in the manual fail validation.
- Harness integration: default Episode/Env messages now use the authoritative
  files; the user message is query-only and metadata is in the shared system
  API. Logs identify `manual_v1`. Custom system overrides require explicit
  `custom_...` provenance. Recursive roots inherit the manual and thinking
  configuration and preserve provider reasoning on subsequent turns.
- Chunk-size default derives from a custom sub-call limit when omitted; explicit
  chunk sizes cannot exceed the limit. Existing configured defaults remain.
- Root requests carry the configured `chat_template_kwargs.enable_thinking`;
  conflicting thinking settings and request-level chat-template overrides fail.
- [M3 tests](../tests/test_prompts.py), strengthened existing harness/rollout
  assertions, `make test-m3`, `make prompts-prepare`, and `make prompts-check`.
  [PROMPTS.md](PROMPTS.md) documents usage and boundaries; the harness guide and
  verified API catalog are updated.

### Commands and outcomes

All commands ran from `rlm-opsd/` with `.venv/bin/python`. Initial tests were
written before implementation, and review regressions failed before their fixes.
Failed logs were retained. No skip, xfail or weakened suffix/privacy assertion
was used to obtain a pass.

| Commands / activity | Observed result | Log |
|---|---|---|
| `pwd`, `rg --files`, ordered `cat` reads, pinned harness/client/rendering source inspection, `git status` | M3 contract and existing integration points located; project remains untracked in parent Git repository | Source/API findings retained in [07](logs/m3/07-api-catalog.log) |
| `make test` before M3 | 3 M0 checks and 92 pytest tests passed. The shell wrapper then exited 1 because `status` is read-only in zsh; subsequent wrappers use `task_exit_code`. No test failed. | [00 baseline](logs/m3/00-baseline.log) |
| Primary Qwen model/template lookup; HF metadata and exact-revision tokenizer/template/license downloads; SHA-256 and installed API inspection | User-selected source pinned; tokenizer-only artifacts cached | [01 source](logs/m3/01-tokenizer-source.log) |
| `pytest tests/test_prompts.py -q --tb=short` before implementation | 21 failed: absent prompt package and invalid chunk-size default behavior | [02 red contracts](logs/m3/02-red-contracts.log) |
| Implement builders/alignment/config; rerun M3 file | 17 passed, 4 failed: harness not connected; test fixture assumed trailing system whitespace survives the Qwen template | [03 first implementation](logs/m3/03-builders-and-alignment.log) |
| Read the pinned template's `\|trim` branches; correct exact fixture expectation; add CLI/harness/thinking tests; run M3 and verifiers files | 20 passed, 7 failed: expected missing CLI, custom provenance checks and harness/request integration | [04 integration red](logs/m3/04-harness-and-cli-red.log) |
| Implement CLI and harness paths; `pytest tests/test_prompts.py tests/test_harness.py tests/test_verifiers_env.py -q --tb=short` | 54 passed; existing upstream warning remains | [05 integration](logs/m3/05-prompt-harness-integration.log) |
| `make prompts-prepare`; `make prompts-check` | Cached artifact hashes verified; actual Qwen tokenizer suffix equality passed with thinking on/off | [06 real tokenizer](logs/m3/06-real-qwen-tokenizer.log) |
| Inspect installed tokenizer signatures/source; fetch server-pinned Transformers `tokenization_utils_base.py`; catalog pinned client/server keys, project signatures and hashes | Source-verified local/server template API contracts; no server execution | [07 catalog](logs/m3/07-api-catalog.log) |
| Separate read-only review of SPEC/plan and M3 files | Found recursive thinking loss, direct-constructor source-check bypass, and request template override gap | [10 review record](logs/m3/10-review.md) |
| Add regressions; `pytest tests/test_prompts.py -k 'forged or recursive_roots or override_pinned' -q --tb=short` | 4 failures reproduced before fixes | [08 review red](logs/m3/08-review-regressions-red.log) |
| Fix validated builder construction, recursive settings/reasoning and override rejection; `make test`; `python -m compileall -q rlm_opsd tests`; `make prompts-check` | 3 M0 + 120 pytest tests passed; compilation and both real tokenizer checks passed | [09 final verification](logs/m3/09-final-tests.log) |
| Documentation links, source/input/artifact hashes, pin equality, whitespace and milestone-scope audit; `git diff --check`, `git status` | Final artifact results retained | [11 artifact review](logs/m3/11-artifact-review.log) |

### Token alignment evidence

The fixture regression uses a real BPE tokenizer and an intentionally unmerged
token pair: decoding/re-encoding it changes its segmentation. Alignment preserves
those original IDs plus role markers, an observation and a later assistant turn.
Other tests reject a wrong/truncated prefix and invalid IDs, check empty suffixes,
and verify that inputs are not mutated. See the
[passing final suite](logs/m3/09-final-tests.log).

The real Qwen smoke produced the following counts for its fixed synthetic
query/context, from [09](logs/m3/09-final-tests.log):

| Mode | Student prefix tokens | Teacher prefix tokens | Copied suffix tokens | Exact suffix equality |
|---|---|---|---|---|
| Thinking on | 205 | 2,125 | 31 | true |
| Thinking off | 207 | 2,127 | 31 | true |

These are tokenizer results, not model outputs or quality measurements. The
suffix checksum was identical in both runs. The log visibly reports that PyTorch
is absent; tokenizer-only execution succeeds without it. The existing upstream
`importlib.abc.Traversable` deprecation warning is unchanged.

### Review findings and verification scope

Every review finding was addressed with a failing regression followed by the
passing full suite. The template override gap was treated as a correctness issue
because a local prefix could otherwise disagree with a server request. The review
covered prompt implementation; documentation received a separate artifact audit.
GPU/model behavior and server parity require deployment checks.

**Verification scope:** prompt construction and exact token-ID suffix copying
with the pinned Qwen tokenizer. The training sample builder uses this prefix
replacement primitive for teacher causal-position mapping. Weight loading, Qwen
inference, server/tokenizer parity, teacher gate and training require the server
checks for those components. The M2 loader requires complete held-out coverage.

## M4 — behavior detectors, offline reports and token categories (2026-10-09)

**Complete.** M4 only, per the user's explicit milestone boundary. Re-read
AGENTS and its listed source documents; used test-first implementation and
separate review. The plan is
[recorded here](superpowers/plans/2026-10-09-m4.md).

### Built

- [D1–D19 analysis](../rlm_opsd/detectors/evaluate.py) over
  [bounded AST facts](../rlm_opsd/detectors/facts.py): alias/provenance tracking,
  search/window/chaining facts, actual subcall statistics, storage/reuse,
  finish/error checks, coverage and task-tag matching. Missing or unsupported
  evidence remains unknown and cannot satisfy a required tag.
- [Strict detector config](../configs/detectors.yaml), with operational values
  left required/unset. The hand-labelled tests use separate explicit thresholds;
  no gate/exit acceptance threshold was selected.
- [Token categories and supplied-divergence summaries](DETECTOR_CATEGORIES.md):
  prose/code/comment/protocol, Unicode character offsets, boundary/special
  tokens, category/turn means and highest-value positions. Sampled logprob
  deltas remain distinct from full KL. No divergence is computed from models.
- [Source-linked Markdown/CSV reports](DETECTOR_REPORTS.md), with before/teacher/
  after phases, family/bucket/domain breakdowns, known/unknown denominators,
  pooled syntax rate, weighted prompt statistics and optional supplied success.
  Missing phases are explicitly `not run`.
- [Offline CLI](DETECTOR_CLI.md), preserved
  [fixture manifest/config/trajectories](../tests/fixtures/detectors/manifest.json),
  and an executed [fixture report](logs/m4/fixture-report/behavior.md)
  ([CSV](logs/m4/fixture-report/behavior.csv)). Its phase labels and values are
  fixture demonstrations, not model measurements.
- Backward-compatible optional `context_metadata` and `size_bucket` fields in
  trajectory logs. New geometry is validated and contains only type/lengths;
  context text/prefix is not added. Legacy logs can supply geometry externally.
- `make test-m4`, [usage/limitations](DETECTOR_USAGE.md), and
  [verified APIs](VERIFIED_APIS.md#m4-additions-offline-behavior-analysis-and-token-categories).

### Commands and outcomes

Commands ran from `rlm-opsd/` using `.venv/bin/python`. Failed red logs are
retained. No test was skipped, xfailed, or weakened to obtain a pass. The listed
pytest shorthand means `.venv/bin/python -m pytest`; root detector invocations
used `-q --tb=short`.

| Command / activity | Observed result | Evidence |
|---|---|---|
| Ordered repository reads, source inspection, baseline `make test` | 3 M0 checks + 120 pytest tests passed | [00 baseline](logs/m4/00-baseline.log) |
| `pytest tests/test_detectors.py` before implementation | 51 failures: missing detector package API | [01 red](logs/m4/01-detectors-red.log) |
| Implement core; rerun same file | 51 passed | [02 green](logs/m4/02-detectors-first-green.log) |
| Add alias/prompt/false-comprehension/window/iteration/control-transfer regressions; rerun | 5 failed / 54 passed, then 59 passed after fixes | [03 red](logs/m4/03-edges-red.log), [04 green](logs/m4/04-edges-green.log) |
| Add review regressions for whole slices, helpers, pattern values, error coverage and prompt-size facts | 7 failed / 61 passed, then 68 passed | [05 red](logs/m4/05-review-red.log), [06 green](logs/m4/06-review-green.log) |
| Add scalar-position and bounded-provenance checks | 2 failed / 70 passed, then 72 passed | [07 red](logs/m4/07-bounds-red.log), [08 green](logs/m4/08-bounds-green.log) |
| Add plan-only finish, impossible-count and executable-default regressions | 5 failed / 72 passed, then 77 passed | [09 red](logs/m4/09-final-edges-red.log), [10 green](logs/m4/10-final-edges-green.log) |
| `pytest tests/test_detector_categories.py -q`; Unicode/newline regressions | Initial 45 missing-feature failures; final 47 passed | [red](logs/m4/categories-red.log), [first green](logs/m4/categories-green.log), [Unicode red](logs/m4/categories-unicode-red.log), [Unicode green](logs/m4/categories-unicode-green.log), [final](logs/m4/categories-final.log) |
| Inspect installed stdlib/tokenizer APIs; cached Qwen offset smoke with offline flags | Actual 30-token fixture classified, including duplicate Unicode offsets; obsolete private API lookup corrected | [API](logs/m4/categories-api.log), [lookup investigation](logs/m4/categories-tokenizer-api-investigation.log), [offset smoke](logs/m4/categories-tokenizer-smoke.log) |
| `pytest tests/test_detector_reports.py -q`; report validation/absent-phase regressions | Initial 33 failures; final 36 passed | [red](logs/m4/reports-red.log), [first green](logs/m4/reports-green.log), [validation red](logs/m4/reports-validation-red.log), [validation green](logs/m4/reports-validation-green.log), [absence red](logs/m4/reports-absent-red.log), [final](logs/m4/reports-absent-green.log) |
| `pytest tests/test_detector_trace_metadata.py -q` | 29 failures / 4 existing rejections before extension; 33 passed after | [red](logs/m4/trace-metadata-red.log), [green](logs/m4/trace-metadata-green.log), [API](logs/m4/trace-metadata-api.log) |
| `pytest tests/test_detector_cli.py -q`; CLI + report tests | 20 initial failures; 20 CLI tests passed, 56 combined passed | [red](logs/m4/reports-cli-red.log), [integration](logs/m4/reports-cli-integration.log), [combined](logs/m4/reports-cli-green.log) |
| Initial report-agent `make test` during concurrent core implementation | 51 missing-core-API failures / 200 passed; superseded by final suite | [intermediate regression](logs/m4/reports-regression.log) |
| Duplicate agent `make test` during final integration | Intentionally interrupted at parent request; not a full-suite result | [interruption record](logs/m4/reports-cli-regression.log) |
| Separate read-only review and exact-reproduction closure | All seven reported issues resolved with regressions; no category/report/metadata finding required a fix | [review](logs/m4/14-review.md) |
| Final `make test` | **3 M0 checks + 333 pytest tests passed**, one existing upstream deprecation warning | [11 full suite](logs/m4/11-full-suite.log) |
| Installed/source signature/hash inspection via Python `inspect` | Exact AST, YAML, config and public project interfaces catalogued | [12 API catalog](logs/m4/12-api-catalog.log) |
| Offline CLI fixture command below; final regeneration with `--overwrite` | Source-linked fixture Markdown/CSV generated; after phase absent | [initial exact command](logs/m4/reports-cli-fixture.log), [13 final run](logs/m4/13-fixture-report-final.log) |
| `make test-m4` | 213 M4 tests passed | [15 M4 target](logs/m4/15-m4-target.log) |
| Source/input hashes, relative documentation links, fixture CSV/source links, whitespace and scope audit; `git diff --check`, `git status --short` | Final artifact audit, including unchanged spec/prompt/data pins | [16 artifact audit](logs/m4/16-artifact-audit.log) |

Executed final fixture command:

```bash
.venv/bin/python -m rlm_opsd.detectors \
  --config tests/fixtures/detectors/fixture-config.yaml \
  --manifest tests/fixtures/detectors/manifest.json \
  --output docs/logs/m4/fixture-report \
  --source-label 'Hand-labelled fixtures; not model results' --overwrite
```

### Verification limits

The analyzer is conservative static analysis, not arbitrary Python execution.
Dynamic loops/branches, arbitrary helpers and unavailable runtime locations
produce unknown evidence. Coverage is the union of supplied input ranges, not
proof that every character was semantically processed. Plan-only finish detection
uses a documented English heuristic. The report and usage guides detail these
boundaries and aggregation denominators. Operational detector thresholds remain
unset for the user to choose; fixture thresholds are not production defaults.

**Verification scope:** offline fixture analysis, detector aggregation and token
categories. Model inference, KL/logprobs, checkpoint comparisons and retention
require model execution and source-linked traces. The server and decontamination
requirements described under M0 and M2 apply to those runs.

## M5 — teacher gate and preflight validation

Date: 2026-10-09. Scope: SPEC §5 teacher gate, plus the user's explicit update
to SPEC §6 making OPSD primary. **Verification covers CPU and HTTP fixtures.**
The attempted operational `make teacher-gate` stopped before any request:
no endpoint URLs, unset user-controlled gate/detector thresholds, and incomplete
held-out decontamination coverage. Fixture evidence is not a model result.
The implementation is locally verified: final `make test` passed **3 M0 checks
and 374 pytest tests**, including all 38 M5 tests and the sandbox regressions.
One existing upstream deprecation warning remains visible.

### Inputs, design and deliverables

Read AGENTS.md and all listed files in order, then the existing M0–M4 code,
progress and verified source contracts. Used the existing specification as the
authorized design, recorded the [M5 plan](superpowers/plans/2026-10-09-m5.md),
and wrote failing tests before production code. The shared project remains
untracked in its parent repository; no branch move, commit or push was made.

- [Gate implementation](../rlm_opsd/eval/gate.py), [config](../configs/gate.yaml)
  and [usage](TEACHER_GATE.md): paired initial-base generation under x and y*,
  fixed dev order/sampling, persistent REPL, separate frozen leaf client,
  original completion IDs/reasoning when supplied, and source-linked evidence.
- Strict no-network preflight checks model/template pins, environment-variable
  names, complete decontamination and every eligible dev family/bucket group.
  It uses the normal M2 loader; answers are stripped and no inspection bypass is
  offered. Operational thresholds remain unset for the user to choose.
- Gate decisions use only teacher behavior, inclusive explicit bounds, minimum
  known counts and maximum unknown fractions. Missing evidence is inconclusive;
  infrastructure errors override threshold results. No correctness reward runs.
- `make teacher-gate`, `make teacher-gate-check`, `make test-m5`; the gate writes
  `run.json`, requests, raw traces, analyses, behavior Markdown/CSV and decisions.
  It preserves partial failures and refuses to overwrite an existing run.
- Failure handling covers HTTP errors/timeouts/model-alias mismatch, provider
  exception text, construction/analysis/cleanup, and recursive child workers.
  Child setup/execution/cleanup failures cannot pass through a recovered root.
- Full regression exposed a pre-existing sandbox cleanup race. Deterministic
  regressions preceded the fix: signal the process group once, await reaping
  before a resource-limit error, and preserve initial permission failures.

### User-authorized OPSD change

[SPEC §6](SPEC.md#6-opsd-training) now selects full-vocabulary masked JSD from
two in-trainer passes on aligned rollout token IDs. The teacher uses the frozen
initial base with the adapter contribution disabled. There
is no scoring server/API. Endpoints serve generation only: student rollouts,
teacher-gate policies and frozen leaf calls. Privileged prefixes still differ,
while the scored suffix IDs and causal positions must align.

[VERIFIED_APIS](VERIFIED_APIS.md#opsd-verified-adapter-residual-off-mechanism-in-pinned-prime-rl)
records exact pinned files/symbols and the full-logit config. prime-rl uses custom
MultiLoRA, with no built-in `disable_adapter()` context. The verified mechanism
zeros/restores cached scaling tensors in place and preserves token routing.
Zero scaling executes adapter kernels/dropout, so the current frozen-teacher
context uses a computational bypass with state restoration. CPU coverage of that
context and the JSD trainer is described under M6–M7 and native integration; GPU
equivalence requires server validation. The M5 source audit covered the baseline
mechanism, and SPEC sections outside §6 were byte-preserved.

### Commands and outcomes

Commands ran from `rlm-opsd/` with `.venv/bin/python`; `pytest` below abbreviates
`.venv/bin/python -m pytest`. Failed red/regression runs remain in the logs.
No tests were skipped, xfailed, or weakened to obtain a pass.

| Command / activity | Observed result | Evidence |
|---|---|---|
| Ordered inputs, baseline `make test` | 3 M0 checks + 333 pytest tests passed | [00 baseline](logs/m5/00-baseline.log) |
| Installed source/signature/hash inspection; environment variable names and local port availability | Exact generation/loader APIs catalogued; no configured inference endpoint found | [01 source API](logs/m5/01-source-api.log) |
| `pytest tests/test_teacher_gate.py -q --tb=short`, config/preflight/decision stage | 19 failures before implementation; then 19 passed | [02 red](logs/m5/02-config-preflight-red.log), [03 green](logs/m5/03-config-preflight-green.log) |
| Same file, real-REPL/local-HTTP paired runner stage | 5 new failures / 19 passed; then 24 passed | [04 red](logs/m5/04-runner-red.log), [05 green](logs/m5/05-runner-green.log) |
| `pytest tests/test_teacher_gate_cli.py -q --tb=short` | 4 failures before CLI/targets; then 4 passed | [06 red](logs/m5/06-cli-red.log), [07 green](logs/m5/07-cli-green.log) |
| Six initial review regressions, then both M5 test files | 6 failures before fixes; then 34 passed | [08 red](logs/m5/08-review-red.log), [09 green](logs/m5/09-review-green.log) |
| Pinned prime-rl HEAD/hash/excerpt/AST inspection and installed-byte comparison; SPEC section/hash assertions | Custom MultiLoRA and full-logit contracts verified from source; no GPU import/forward | [10 source verification](logs/m5/10-mode-b-source-verification.log) |
| First full `make test` | 3 M0 checks; 366 passed / 1 existing CPU-limit cleanup failure | [11 regression failure](logs/m5/11-full-suite.log) |
| `make teacher-gate-check`; `make teacher-gate` with operational config | Both not_run, exit 2, no model request or operational report | [12 readiness](logs/m5/12-readiness.log), [13 real attempt](logs/m5/13-real-gate-attempt.log) |
| Instrumented repeat of real CPU-limit test (up to 8 planned, stopped on failure at iteration 2) | Repeated signals observed; EOF surfaced before worker return code was ready | [14 investigation](logs/m5/14-cleanup-investigation.log) |
| `pytest tests/test_harness.py -q -k 'cleanup_is_idempotent or waits_for_worker_exit or initial_permission' --tb=short`; then harness and both M5 files | 2 failed / 1 passed before fix; then 64 passed | [15 red](logs/m5/15-cleanup-red.log), [16 green](logs/m5/16-cleanup-green.log) |
| `make test` after cleanup fix | 3 M0 checks + 370 pytest tests passed | [17 regression](logs/m5/17-full-suite.log) |
| `pytest tests/test_teacher_gate.py -q -k recursive_worker --tb=short` before recursive fix | 3 false-pass failures; budget-only control passed | [18 red](logs/m5/18-recursion-red.log) |
| `pytest tests/test_teacher_gate.py tests/test_teacher_gate_cli.py tests/test_harness.py -q --tb=short` after recursive fix | 68 passed | [19 green](logs/m5/19-recursion-green.log) |
| Separate read-only reviews and follow-up closure | Reported issues addressed test-first; no further substantive findings | [20 review](logs/m5/20-review.md) |
| `.venv/bin/python docs/logs/m5/run_http_fixture.py` | First attempt failed before a run because the script directory hid the project import; added repository to sys.path, removed only the newly created empty output directory, then reran successfully | [21 initial failure](logs/m5/21-http-fixture.log), [21 successful CLI run](logs/m5/21-http-fixture-green.log) |
| Final `make test` | **3 M0 checks + 374 pytest tests passed**, one upstream deprecation warning | [22 final full suite](logs/m5/22-full-suite-final.log) |
| Python source/input hashes, documentation/source links, fixture evidence, syntax/whitespace and scope assertions; `git diff --check`, `git status --short`, pinned source status | Audit passed; unchanged prompt/task/data pins and intended SPEC hash verified | [23 artifact audit](logs/m5/23-artifact-audit.log) |

### Preserved fixture demonstration

The [reproduction script](logs/m5/run_http_fixture.py) starts a local HTTP fixture
and invokes the actual `make teacher-gate` CLI with fixture-only inputs. Its
[report](logs/m5/http-fixture/report/gate.md),
[behavior Markdown](logs/m5/http-fixture/report/behavior.md) and
[CSV](logs/m5/http-fixture/report/behavior.csv) link the executed REPL traces.
It completed 12 episodes (6 paired tasks), 24 root and 12 leaf requests, all to
synthetic HTTP responders; [counts](logs/m5/http-fixture/fixture-summary.json)
and the command log provide evidence. Every report is labelled
**TEST HTTP FIXTURE; NOT MODEL RESULTS**. The fixture's asserted coverage and
thresholds are confined to test inputs; operational data/configs are unchanged.

### Verification limits

**Verification scope:** scripted HTTP generation and CPU harness integration.
The operational attempt stopped at preflight and produced no gate report. Local
preflight checks aliases; deployment weight/template identity is operator-declared.

Teacher-gate acceptance requires generation endpoints, user-selected
gate/detector values and a fully decontaminated dev pool, followed by the
documented `make teacher-gate`. Operational thresholds and the teacher manual
retain their configured values; fixture evidence does not authorize changing them
or bypassing coverage. M0 server and M2 held-out data requirements apply.

## M6 — shared frozen-teacher infrastructure

The aligned sample builder, frozen-teacher context, guarded model loader,
small-model pins and real gate validation remain in use by OPSD. Their original
CPU evidence is retained in [the historical run log](logs/m6/21-full-suite.log).
The current JSD trainer and commands are documented in [OPSD.md](OPSD.md).
Pretrained small/27B acceptance requires the GPU smoke commands and server
prerequisites in that guide. This section records the shared infrastructure
and its CPU evidence; historical logs are unchanged.

## M7 — primary full-vocabulary JSD and optional detached token gate

Date: 2026-10-09. **M7 implementation is complete and locally verified.**
The JSD implementation and its CPU evidence are described below; current names
are used for artifacts. Linked historical logs retain their original names.
Final `make test`: **3 M0 checks + 501 pytest tests passed**, including
**74 M7 tests**. Fourteen upstream torch JIT deprecation warnings and the
existing Verifiers deprecation remain visible. No tests were skipped, xfailed,
silenced or weakened. Predeployment small/27B acceptance requires GPU execution
on the configured server.

### What changed

Read AGENTS.md and every file it lists, then the M6 trainer, verified source
contracts and logs. The [M7 plan](superpowers/plans/2026-10-09-m7.md) records
the existing SPEC as the authorized design, task interfaces, tests and scope.
Used inline test-first implementation and an independent read-only review.
The shared project remains untracked in its parent repository; no worktree,
branch move, commit or push was performed. No dependencies were installed.

- [JSD objective](../rlm_opsd/training/jsd.py): exact full-vocabulary beta=0.5
  JSD with natural logarithms. Teacher tensors are detached; masks select root
  assistant targets only. The optional detached gate is
  `sigmoid(k * (log pT(target) - log pS(target)))`, default off. Both variants
  normalize by selected-token count; empty masks safely contribute zero.
- Vocabulary projection occurs only after selecting aligned hidden rows, in
  configurable row chunks. A custom first-order autograd function saves hidden
  states/head references and recomputes one projection/loss chunk per backward
  iteration. It does not retain every chunk's graph, project whole sequences,
  copy the full head to FP32, or approximate the vocabulary with top-k.
- [OPSD trainer](../rlm_opsd/training/opsd.py): actual backbone passes under
  the existing serialized M6 frozen-teacher context; restores adapter/routing/
  mode/RNG state before backward. Uses the frozen ordinary head and updates
  only LoRA. Tests compare values and gradients against an independent dense
  reference across multi-turn samples and activation checkpointing.
- [Configuration](../configs/opsd.toml),
  [small model config](../configs/opsd_small.toml), factory and runner
  select OPSD end-to-end. New keys: fixed `jsd_beta=0.5`,
  `jsd_chunk_size=64`, `token_gate=false`, positive finite `token_gate_k=1.0`.
  `make opsd`, `make opsd-check`, `make test-m7` are available. The direct
  training CLI defaults to the 27B OPSD configuration.
- Smoke reports include objective identity. The 27B OPSD stage
  requires real small OPSD evidence with matching beta, temperature and gate
  settings, plus its checkpoint hash. Existing
  gates, complete decontamination, cached exact weights and CUDA checks remain
  mandatory; no test override is exposed.
- [Usage](OPSD.md) and [verified APIs](VERIFIED_APIS.md#m7-primary-full-vocabulary-jsd-and-optional-token-gate)
  record exact interfaces, config keys, mathematical formula and runtime limits.
  SPEC, prompts/manual, tokenizer/model pins, operational thresholds and task
  data were preserved.

### Commands and results

Commands ran from `rlm-opsd/`; `pytest` below means `.venv/bin/python -m pytest`.
All failed red runs are retained. Numerical/CPU fixture values are not model
performance results.

| Command / activity | Observed result | Evidence |
|---|---|---|
| Ordered input/source reads, workspace status; baseline `make test` | 3 M0 checks + 427 pytest tests passed | [00 baseline](logs/m7/00-baseline.log) |
| Python `inspect`/hash/source inspection of installed torch autograd and pinned prime-rl head boundary | Signatures/source verified before custom autograd implementation | [01 source API](logs/m7/01-source-api.log) |
| `pytest tests/test_training_jsd.py -q --tb=short`, dense stage | 22 missing-feature failures, then 22 passed | [02 red](logs/m7/02-jsd-red.log), [03 green](logs/m7/03-jsd-green.log) |
| Same file, `-k 'chunk or low_precision_projection'`, then whole file | 17 missing-feature failures, then 39 passed. Includes independent dense gradients, finite differences, BF16/FP16, tail-vocabulary sensitivity, bounded projection and saved-tensor observations | [04 red](logs/m7/04-chunk-red.log), [05 green](logs/m7/05-chunk-green.log) |
| JSD trainer tests, then combined numerical/model tests | 16 missing-feature failures, then 55 passed, including actual MultiLoRA and random tiny Qwen3.5 full-attention update | [06 red](logs/m7/06-mode-b-red.log), [07 green](logs/m7/07-mode-b-green.log) |
| Smoke runner tests, then combined training tests | 13 missing-feature failures, then all 121 M6/M7 training tests passed | [08 red](logs/m7/08-runner-red.log), [09 green](logs/m7/09-training-green.log) |
| First `make test` before review regressions were collected | 3 M0 checks + 495 pytest tests passed; superseded by final suite | [10 regression](logs/m7/10-full-suite.log) |
| Independent review; targeted Python overflow-stage reproduction | Finite logits/settings can overflow normalization before JSD multiplication; dense/chunked APIs previously returned NaN | [11 investigation](logs/m7/11-overflow-investigation.log), [19 review](logs/m7/19-review.md) |
| `pytest tests/test_training_jsd.py -q -k normalization_overflow --tb=short`; then `make test-m7` | 4 regression failures before normalized-logprob checks; then 72 M7 tests passed | [12 red](logs/m7/12-overflow-red.log), [13 green](logs/m7/13-m7-green.log) |
| `pytest tests/test_training_jsd.py -q -k unrepresentable_scalars --tb=short`; then `make test-m7` | 2 regression failures before working-precision scalar checks; then **74 passed** | [14 red](logs/m7/14-scalar-red.log), [15 final M7](logs/m7/15-m7-final.log) |
| `.venv/bin/python docs/logs/m7/verify_source.py` | Pinned/installed byte equality, torch/project signatures, both B configs and hand-derived binary-distribution value/gradient verified | [16 source verification](logs/m7/16-source-verification.log), [script](logs/m7/verify_source.py) |
| Final `make test` after all fixes | **3 M0 checks + 501 pytest tests passed**, 15 visible upstream warnings | [17 final suite](logs/m7/17-full-suite-final.log) |
| Small-model smoke preflight and attempted run | Both **not_run**, exit 2: missing real small gate, cached weights and Linux/CUDA; no requests or run directory | [18 small check](logs/m7/18-small-opsd-b-check.log), [18 small attempt](logs/m7/18-small-opsd-b.log) |
| 27B smoke preflight and attempted run | Both **not_run**, exit 2: missing real 27B gate, small OPSD smoke, cached weights and Linux/CUDA; no requests or run directory | [18 27B check](logs/m7/18-27b-opsd-b-check.log), [18 27B attempt](logs/m7/18-27b-opsd-b.log) |
| Python immutable-input/source hashes, syntax/whitespace, relative links, scope and output audit; `git diff --check`/status | Final artifact verification | [20 audit](logs/m7/20-artifact-audit.log), [audit script](logs/m7/audit_artifacts.py) |

### Verification limits

The bounded allocation claim applies to vocabulary projection/divergence
workspace, O(chunk size × vocabulary), plus O(selected positions × hidden)
state/gradient. Frozen head weights and student backbone activations remain.
Peak GPU allocation and total-model memory fit require server measurements. Loss gradients
are first-order only. Inputs whose normalization or scalar arithmetic exceeds
working precision fail explicitly; no clipping/approximation masks the failure.

The standalone smoke performs one synchronous task/update, eager on one GPU
with one dense adapter. Native async transport, weight broadcast, resume and
FSDP are described in [OPSD_TRAIN.md](OPSD_TRAIN.md). Local random Qwen tests
cover full attention with Transformers 5.9.0. Server acceptance requires pinned
pretrained loading, hybrid attention and A100/H100 execution, using the M0/M2/M5
runtime, coverage and gate prerequisites. No teacher scoring API is used.

**Verification scope:** CPU numerical/model tests and guarded preflight attempts.
Pretrained small/27B updates, gate-on/off behavior comparisons and peak GPU memory
require server execution. Fixture outputs are labelled as CPU evidence. The JSD
objective and token gate are implemented, tested and selectable by config.

## M8 — OPSD-only monitoring and two-condition exit

Date: 2026-10-09. **M8 server-ready implementation is complete.** Final full
verification: **3 M0 checks + 576 pytest tests passed**, with 15 visible upstream
deprecation warnings. These checks cover CPU and HTTP integration; real
checkpoint behavior and retention acceptance requires server evaluation.
The user explicitly changed M8 during implementation: remove both GRPO-pool
readiness items, move them to the M9 specification, and leave the retention path
plus behavior/retention tolerances required and unset until initial reports are
reviewed. M9 defines the GRPO readiness and handoff criteria in SPEC §9.

### What changed

Read AGENTS.md and every listed file in order. Followed the existing SPEC with
inline test-first implementation, then incorporated the user's revised scope
with new failing tests before changing the implementation. The
[M8 plan and ledger](superpowers/plans/2026-10-09-m8.md) records scope and checks.
[Independent read-only review](logs/m8/28-review.md) found two issues, both fixed
with red/green regressions. No dependencies were installed; model/tokenizer/
upstream pins and task data remain unchanged. The project is still untracked
in its parent repository; no commit, branch move or push was performed.

- [Behavior runner](../rlm_opsd/eval/monitor.py): evaluates every fixed
  `dev_behavior` task as base + x, base + y*, and checkpoint + x. Uses the real
  RLM harness and pinned generation clients, frozen leaf endpoint, exact saved
  native adapter, and source-linked detector reports. No answers enter prompts.
  Behavior evaluation requires no retention set or exit tolerance.
- [Local KL scoring](../rlm_opsd/eval/scoring.py): full-vocabulary KL(T||S) at
  aligned root targets, chunked projection, no gradients or optimization.
  Original rollout IDs supply both suffixes; offset lookup must round-trip
  exactly and never supplies scored IDs. Teacher uses the M6 true LoRA bypass;
  state and module flags are restored. KL is reported overall, by category and
  turn, with top text positions and readable trajectories under
  `review/step_<n>/<family>/`.
- [Exit](../rlm_opsd/eval/exit.py) validates complete behavior evidence and
  recomputes its summaries, then runs [paired retention](../rlm_opsd/eval/retention.py)
  through the base/checkpoint generation endpoints. It compares only detector
  agreement with teacher-as-policy and retention drop from base. Invalid gold
  fails before requests; missing evidence is inconclusive; infrastructure
  failures cannot pass. Decimal boundary comparisons account only for binary64
  roundoff, without setting performance tolerances.
- [Configuration](../configs/eval.yaml) and [exit settings](../configs/exit.yaml)
  expose `make eval-behavior`, `make exit-check`, and local `-check` targets.
  The exit file has required unset `retention_path`, `behavior_tolerance`, and
  `retention_tolerance`, plus explicit evidence sufficiency settings. Periodic
  evaluation checks `checkpoint_step % eval_interval`; the checkpoint driver
  calls it. Multi-step training and adapter publication use the native integration
  described in [OPSD_TRAIN.md](OPSD_TRAIN.md).
- Updated [SPEC §7–9](SPEC.md#7-monitoring) and [AGENTS M8/M9](../AGENTS.md)
  exactly for the requested phase boundary. Pass@k, entropy on the GRPO pool,
  and its mixed pass/fail criterion are M9 prerequisites before any GRPO step.
  Their initial M8 implementation and tests were removed before
  delivery. Earlier logs preserve that superseded work honestly.
- [Usage](MONITORING.md) and [verified APIs](VERIFIED_APIS.md#m8-opsd-only-monitoring-and-two-condition-exit)
  document exact settings, entry points, source files, evidence format and limits.

### Commands and results

Commands ran from `rlm-opsd/`; `pytest` means `.venv/bin/python -m pytest`.
HTTP fixtures and CPU tensors are test evidence, never model-performance runs.

| Command / activity | Observed result | Evidence |
| --- | --- | --- |
| Ordered input/source reads, status, baseline `make test` | 3 M0 checks + 501 pytest tests passed | [00 baseline](logs/m8/00-baseline.log) |
| Initial `pytest tests/test_monitor_metrics.py tests/test_exit_check.py -q --tb=short` | 34 missing-feature failures, then 34 passed; later revised to OPSD-only scope | [01 red](logs/m8/01-metrics-red.log), [02 green](logs/m8/02-metrics-green.log) |
| Inspect torch checkpoint, Verifiers rollout/client and tokenizer offset APIs; execute Unicode token fixture | Actual signatures, paths and Unicode offsets recorded | [03 APIs](logs/m8/03-source-api.log) |
| `pytest tests/test_monitor_scoring.py -q --tb=short` | 12 missing-feature failures, then 12 passed; entropy portion later removed per user | [04 red](logs/m8/04-scoring-red.log), [05 green](logs/m8/05-scoring-green.log) |
| Initial runner and divergence summary tests before/after implementation | 14 + 1 red failures; then 37 runner/metrics tests passed | [06 runner red](logs/m8/06-runner-red.log), [07 summary red](logs/m8/07-summary-red.log), [08 green](logs/m8/08-runner-green.log) |
| CLI tests before/after implementation | 5 red failures; first green attempt exposed 2 Make executable-path quoting failures; quoted M8 Python paths, then 5 passed | [09 red](logs/m8/09-cli-red.log), [10 quoting failure](logs/m8/10-cli-green.log), [11 green](logs/m8/11-cli-green.log) |
| Initial evidence replay regressions | 5 red failures; first fix exposed JSON tuple/list normalization in detector facts; normalized comparison, then 28 passed | [12 red](logs/m8/12-evidence-red.log), [13 normalization failure](logs/m8/13-evidence-green.log), [14 green](logs/m8/14-evidence-green.log) |
| User's OPSD-only revision: revised behavior/exit, separate retention, and KL-only tests before code changes | 13 scope failures; 7 separate-retention/config failures; 3 KL-only failures. Existing controls passed | [15 scope red](logs/m8/15-opsd-scope-red.log), [16 retention red](logs/m8/16-retention-red.log), [17 KL red](logs/m8/17-kl-only-red.log) |
| `make test-m8` after scope revision | First run: 63 passed / 1 fixture assertion failure. Source shows Verifiers translates `max_tokens` to `max_completion_tokens`; corrected the emitted-key assertion while preserving the value 32 | [18 run](logs/m8/18-opsd-only-green.log) |
| New exit-preflight provenance regression; subsequent M8 run and focused retention verification | Regression red on descriptive endpoint-identity wording; fix preserves all hash/pin checks. Interim M8 run: 64 passed / same provider-key assertion; corrected focused run: 7 passed | [19 red](logs/m8/19-retention-provenance-red.log), [20 interim](logs/m8/20-opsd-only-green.log), [21 green](logs/m8/21-retention-green.log) |
| First OPSD-only full `make test` before review regressions | 3 M0 checks + 566 pytest tests passed | [22 full suite](logs/m8/22-full-suite.log) |
| Review regression command: `pytest tests/test_retention.py tests/test_exit_check.py -q -k 'invalid_gold or decimal_rate' --tb=short`; then both files | 10 failures before fixes; all 36 retention/exit tests passed after fixes | [23 red](logs/m8/23-review-red.log), [24 green](logs/m8/24-review-green.log) |
| Final post-review `make test` | **3 M0 checks + 576 pytest tests passed**, 15 visible upstream deprecation warnings | [25 final suite](logs/m8/25-full-suite-final.log) |
| `.venv/bin/python docs/logs/m8/verify_source.py` | Installed/pinned source byte equality, exact signatures/config fields and executed offset mapping; CUDA false | [26 source verification](logs/m8/26-source-verification.log), [script](logs/m8/verify_source.py) |
| `make eval-behavior-check`; `make eval-behavior` | Both **not_run**, exit 2; unset checkpoint/endpoint/step settings. No model requests or evaluation output directory | [27 check](logs/m8/27-eval-behavior-check.log), [27 attempt](logs/m8/27-eval-behavior.log) |
| `make exit-check-check`; `make exit-check` | Both **not_run**, exit 2; required retention path, checkpoint identity and acceptance settings unset. No model requests or exit output directory | [27 check](logs/m8/27-exit-check-check.log), [27 attempt](logs/m8/27-exit-check.log) |
| Final `make test-m8` | **75 passed**, 14 visible upstream torch JIT deprecation warnings | [29 M8 final](logs/m8/29-m8-final.log) |
| `.venv/bin/python docs/logs/m8/audit_artifacts.py`; `git diff --check` | Preservation, config scope, syntax, source cleanliness, relative links, whitespace and no fabricated run outputs verified | [30 audit](logs/m8/30-artifact-audit.log), [audit script](logs/m8/audit_artifacts.py) |

### Runtime requirements and verification scope

Local coverage includes actual pinned MultiLoRA CPU scoring against an
independent dense KL calculation, projection bounds, no gradients, Unicode
alignment, atomic checkpoint validation, real HTTP clients/harness execution,
partial-failure logs, source-evidence replay, user-required settings, and
hand-derived exit boundaries. This evidence establishes protocol and numerical
behavior; model quality requires checkpoint evaluation.
No tests are skipped or xfailed and no operational thresholds are filled in.

Real evaluation requires the pinned Linux/CUDA server, cached weights, an OPSD
checkpoint served by the generation endpoint, complete held-out decontamination
and a passed teacher gate. Retention/exit additionally requires the user's dataset
and tolerances. Endpoint weight/template identity is operator-declared. GPU fit
and pretrained 27B behavior/retention require measurements from those runs.
M8 covers monitoring and two-condition exit; SPEC §9 defines the M9 GRPO
readiness and handoff criteria.

## Repository publication preparation

The user requested publishing the completed project to
`https://github.com/pmukeshreddy/Loop`, directly on `main`, with commit email
`mukeshreddy662369@gmail.com`. Existing Git identity already matches. Fetched
`origin` and verified local/remote `main` both at `04b9b1a` before the commit.

Re-ran `make test`: **3 M0 checks + 576 pytest tests passed**, with 15 visible
upstream warnings. [Pre-push test log](logs/m8/31-pre-push-tests.log).
Validated the publication inventory, symlinks and file sizes. Added narrow
ignore exceptions for the 12 scripted M5 HTTP trajectory fixtures required by
regression tests and linked reports. Dependencies, caches and generated context
files remain under their existing ignore rules. No milestone code changed.

Staged source/document whitespace checks pass. Raw historical logs and CSVs
retain their captured whitespace/line endings; they are excluded from that
formatting check. Removed one extra EOF blank line from `eval/metrics.py`.


## QLoRA conversion

Converted the existing smoke and native multi-step loaders to double-quantized
NF4 transformer linear weights with BF16 computation. Embeddings, norms,
convolution parameters and the chunked JSD head remain frozen in BF16. Only
prime-rl MultiLoRA parameters train; the loss, teacher bypass, FSDP wrapping,
rollout transport and adapter synchronization are preserved. The native weight
export now writes adapters over the pinned base; DCP retains full training state.
Old dense-base smoke evidence no longer satisfies the QLoRA prerequisite.

Executed checks:

- `make test`: **3 dependency/source checks and 638 tests passed**, with 33
  visible upstream deprecation/future warnings. Includes source-patch
  reconstruction, NF4 smoke updates with token gate on/off, frozen-base and
  teacher invariance, native adapter export/reload, and two-rank FSDP/DCP resume.
  [Full test log](checks/qlora/make-test.log).
- Final targeted run of `tests/test_training_qlora.py` and
  `tests/test_training_runner.py` after strengthening checkpoint coverage:
  **28 passed**, with 26 visible upstream warnings. Both enabled and disabled
  activation checkpointing reproduce the uninterrupted next update exactly
  after reloading native AppState model/optimizer/scheduler state into a fresh
  NF4 model; an empty-mask rank participates. The prerequisite fixtures also
  carry valid NF4/objective metadata so unrelated failures cannot mask their
  intended assertions. [Checkpoint reload log](checks/qlora/checkpoint-reload.log).
- Source patch verification reports `already_applied`. Source/document
  whitespace check passes excluding the unified patch artifact's required
  blank context lines.

All training checks above use randomly initialized tiny CPU models. Gloo tests
required local socket access outside the sandbox. CUDA/NCCL, pretrained Qwen3.5
training, live vLLM synchronization and 27B memory/throughput require acceptance
checks and measurements on the configured server.
Dependencies and source contracts are recorded in [VERIFIED_APIS](VERIFIED_APIS.md#qlora-storage-and-checkpoint-contracts).

Before publishing to `pmukeshreddy/Loop` on `main`, reran `make test` against
the final tree: **3 dependency/source checks and 639 tests passed**, with 35
visible upstream warnings. [Pre-push test log](checks/qlora/pre-push-test.log).
