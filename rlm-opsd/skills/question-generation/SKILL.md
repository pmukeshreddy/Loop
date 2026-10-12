---
name: question-generation
description: Write new, source-specific DeepSWE engineering tasks grounded in one pinned repository, organized around the RLM behaviors they give practice in, with the executable artifacts (defect, probe or hidden-test patches) needed to verify them. Use after source analysis, once per generation round.
---

# Question generation

You write engineering tasks about one real repository. Each task is a natural
request a maintainer could send to a colleague. The tasks exist to give a
model practice operating as a Recursive Language Model (RLM). The repository
work (tracing, debugging, impact analysis, fixing, implementing) is the
setting; the RLM behaviors are what the task teaches.

## The solver's environment

The task is solved inside a Python REPL. The solver never sees the
repository directly. It receives only metadata, while a REPL variable
`context` holds a list of strings: one per repository file, each starting
with `# File: <path>`, followed by execution logs that start with
`# Log: <title>`. The solver can run Python over these strings, call a
language model on prompts it builds (`llm_query`, roughly 32,000 characters
per call), keep variables across turns, and must finish with `FINAL(...)`
or `FINAL_VAR(name)`. The reference solver investigates the text and never
executes the repository (no imports, no test runs), so the answer must follow
from reading the code, tests, docs and any logs you request. Execution
evidence the solver needs must already be in those logs.

Never mention any of this in the question. The question must read like an
engineering request, not instructions for operating a REPL.

## Behaviors (the primary organization)

Every task lists the behaviors it is meant to exercise and explains which
properties of the task make each behavior useful. Tasks may combine
behaviors. Choose behaviors the task genuinely calls for; do not label a
task with behaviors that a competent solver would not need.

| Behavior | Useful when the task has these properties |
|---|---|
| `inspect_locate` | Large repository context (tens of thousands of characters or more). The relevant evidence is a small, scattered fraction. Names in the request are entry points, but the answer needs following definitions, call sites, registrations or test references found by searching with code. |
| `chunked_subcalls` | Answering requires semantic judgment over more text than fits in one read: several functions, classes, docs or log sections must each be understood. Code can narrow the candidates, but deciding requires reading them, so bounded sub-calls over selected chunks help. |
| `recursive_decomposition` | The investigation splits into independent sub-investigations (per failing test, per caller, per module, per configuration source) whose findings are combined. Focused sub-calls answer the sub-questions. |
| `persistent_state` | Several dependent steps reuse earlier results: a file index, a list of candidate symbols, extracted call edges, file text being edited, partial findings. |
| `combine_verify_finish` | The deliverable is an aggregate built in code (node-ID set, symbol list, a patch assembled from exact file text) that should be checked programmatically before finishing (deduplicate, sort, confirm every hunk's context exists). |
| `direct_solve` | A focused context of only a few files, under 16,000 characters in total, where reading directly is the right call and delegation would waste effort. The task still needs real reasoning, such as simulating code, computing outputs, or spotting a defect. |

Think in the solver's budget: at most 20 turns, and the reading discipline is
small windows of a few thousand characters per turn. Sub-calls are useful when
the text that must be *understood* (not just searched) is larger than the
solver can read in small windows within that budget: dozens of functions or
test cases to judge, long modules, docs and code to reconcile. They are not
useful when one search and a short read decide the answer.

The pipeline runs a reference solver in the real harness and checks that
its execution actually exhibits the behaviors you claim. For example, a
`direct_solve` task whose reference solution needs sub-calls is rejected.
So is a `chunked_subcalls` task the solver can answer with one regex.

## Settings and the verifiable answer kinds

Every task must be verifiable by execution against the repository. Pick an
`answer_kind` whose ground truth the pipeline can compute:

| answer_kind | Ground truth | Required artifacts |
|---|---|---|
| `patch` | The solver's diff is applied to the starting state; tests that failed must pass, all other passing tests must still pass. | `setup_patch` (a realistic defect in non-test code) and usually `include_failure_log: true`; or `hidden_tests_patch` for implementation work. |
| `test_ids` | `probe_patch` (your exact implementation of the planned change described in words) is applied and the suite is run; tests that newly fail are the answer. | `probe_patch`. |
| `symbols` | With `setup_patch`: the functions that patch changed. Without it: an independent verifier executes the repository (for example with tracing) to determine the symbols. | `setup_patch` for diagnosis tasks. |
| `value` | An independent verifier writes a program that imports and runs the repository code to compute the value. | The question must be precise enough to execute. Ask about repository behavior a maintainer needs to know (an effective setting, which units behave a certain way, what a public call returns in a stated situation). Never paste a program and ask what it prints. |

Starting settings (the source analyst may add more):

- `dependency_tracing`: follow calls, registrations, inheritance or config
  flow across modules (usually `symbols`, `value` or `test_ids`).
- `scattered_evidence_debugging`: diagnose or fix a defect whose evidence is
  spread across a log, tests and several modules (`patch` or `symbols`).
- `change_impact`: predict which existing tests a described change breaks
  (`test_ids`).
- `multi_module_fix`: repair behavior that requires coordinated edits in
  more than one file (`patch`).
- `test_failure_investigation`: start from failing tests in a log and find
  the cause (`symbols` or `patch`).
- `implementation`: add a small, well-specified capability that fits the
  existing architecture (`patch` with `hidden_tests_patch`).

Balance the round. Most tasks should start from a concrete defect, a planned
change or a missing capability (`patch`, `test_ids`, `symbols`), because those
need evidence gathered across the repository. Use `value` sparingly. Keep any
code in a question to a few illustrative lines; the pipeline rejects
questions that embed long listings.

## Writing artifacts

All patches are unified diffs against the exact file text you were given:

```diff
--- a/src/pkg/module.py
+++ b/src/pkg/module.py
@@ -120,7 +120,7 @@ def resolve(self, name):
     context line copied exactly
     context line copied exactly
     context line copied exactly
-    original line
+    changed line
     context line copied exactly
```

- Copy context lines character-for-character, including indentation. Keep at
  least three context lines around each change. Line numbers may be
  approximate; context must be exact.
- `setup_patch` introduces one plausible regression of the kind a maintainer
  could make: an off-by-one, an inverted or missing condition, the wrong key
  or attribute, a default not propagated, a cache not invalidated, an
  exception swallowed, a branch for one case applied to another. It touches
  only non-test files. It must not cause syntax errors or import failures,
  delete whole features, rename public APIs, or contain comments that hint
  at the defect. It should break some existing tests but far from most.
  Prefer defects whose symptom shows up away from their cause.
- `probe_patch` implements precisely the change your question describes in
  words, in non-test files only. It must make at least one and at most
  thirty existing tests fail.
- `hidden_tests_patch` adds a **new** test file under the repository's test
  directory (`--- /dev/null` / `+++ b/tests/test_<topic>.py`, a single
  `@@ -0,0 +1,N @@` hunk), so it applies without depending on existing file
  text. It checks only observable behavior named in the question. They must fail on the
  current code and pass for any correct implementation. They must not import
  private helpers the question never mentions.

## Writing the question

- Write natural engineering prose: a ticket, a review question, a CI triage
  request, an on-call question. Specific to this repository and grounded in
  its real names and behavior.
- State the deliverable and its exact format, naturally. Examples: "a JSON
  list of pytest node IDs"; "`path::Qualname` entries"; "a unified diff
  against the repository files, without changing tests"; "a JSON number".
- Include every constraint needed for a unique answer. Avoid hedged phrasing
  that admits several answers.
- Never ask the solver to write, add or edit tests. Implementation and
  repair tasks are verified by hidden acceptance tests and the existing
  suite; the deliverable is the production change only.
- Do not leak the answer. Do not name the defective function in a diagnosis
  task, list the failing tests in an impact task, or describe the fix in a
  repair task.
- Do not prescribe how to work. Never mention REPLs, `context`, searching,
  chunking, sub-calls, recursion, `FINAL`, steps, or tool counts.
- No padding: no backstory that does not constrain the answer, and no
  irrelevant requirements added to look harder.
- It must be impossible to answer from general knowledge of the library or
  of Python. The answer must require examining this snapshot.
- If you request a failure log (`include_failure_log: true`), refer to it
  naturally ("the CI log in the context", "the attached pytest output").
  The pipeline captures the real log after applying your `setup_patch`.

## Exemplars

These illustrate quality. They use fictional projects on purpose: never
reuse their wording, structure or identifiers. Every task you write must
come from the repository in front of you.

Strong:

1. *Scattered-evidence debugging; `patch`; inspect_locate, persistent_state,
   combine_verify_finish.* "CI went red after last week's cleanup of the
   header utilities: the attached pytest log shows the multipart upload tests
   failing on boundary parsing, yet nobody touched the multipart module.
   Track down the root cause and send the fix as a unified diff against the
   repository files. Leave the tests unchanged." Why it is strong: the
   symptom and the cause are in different modules; the log, the test, and
   two layers of helpers must be connected; the patch must be assembled from
   exact file text.

2. *Change impact; `test_ids`; inspect_locate, recursive_decomposition,
   combine_verify_finish.* "We plan to change `Settings.from_env()` so it no
   longer falls back to the legacy `APP_` prefix when the new `SVC_`
   variable is missing; the legacy lookup would be removed entirely. Which
   existing tests would fail after that change? Reply with a JSON list of
   pytest node IDs." Why it is strong: the fallback is reached through
   several callers, each of which leads to different tests, so the
   investigation decomposes per caller; the answer is an exact set.

3. *Dependency tracing; `value`; chunked_subcalls, combine_verify_finish.*
   "For the built-in column types in `types/`, which ones accept a Python
   `Decimal` on assignment without converting it to `float` first? Return
   the class names as a JSON list sorted alphabetically." Why it is strong:
   about twenty classes must each be understood; code narrows the
   candidates, but semantic reading decides; the answer is executable.

4. *Test-failure investigation; `symbols`; inspect_locate,
   recursive_decomposition.* "Three tests in the attached log fail with
   `KeyError: 'charset'` after a refactor. Which function or functions
   contain the change responsible? Answer with `path::Qualname` entries in a
   JSON list." Why it is strong: each failing test leads through a different
   path; the shared cause must be isolated.

5. *Direct solve; `value`.* With only `retry/backoff.py` (about 6,000
   characters) in context: "What delays, in seconds, does
   `CappedBackoff(base=0.5, factor=3, cap=4)` produce for attempts 1 through
   6? Return a JSON list of numbers." Why it is strong: small enough to read
   directly; still requires simulating the code's clamping and rounding.

6. *Implementation; `patch` with hidden tests; inspect_locate,
   persistent_state, combine_verify_finish.* "Add a `strict` flag to
   `Loader.load()` that rejects unknown keys at every nesting level, not
   only at the top, raising the existing `ValidationError` with the dotted
   path of each unknown key. Deliver the change as a unified diff." Why it
   is strong: the nesting is handled in a different module from the entry
   point, so the change must follow the data through both.

Weak (rejected):

- "Which file defines `Parser`?" Trivial lookup: one search answers it.
- "What is the default value of `timeout` in `Client.__init__`?" Trivial lookup.
- "Explain how the caching layer works." Free-form and not verifiable.
- "In Python, what does `functools.lru_cache` do with unhashable arguments?"
  Answerable without the repository.
- "Search the files with a regex, split the matches into chunks and ask a
  sub-model about each." Prescribes RLM operations.
- Ten questions of the form "Which tests call `X`?" with `X` swapped.
  Template output with renamed identifiers.
- A two-paragraph story about a team offsite before a one-line question.
  Artificial padding.
- A 40-line script exercising several unrelated behaviors, followed by
  "what JSON object does this program produce?". That is a quiz, not an
  engineering request. Ask about one behavior a maintainer would actually
  need to know, and include only the code that question requires.

## Output

Return one fenced `json` block: `{"tasks": [ ... ]}`. Each task object has:

```json
{
  "setting": "scattered_evidence_debugging",
  "primary_behavior": "inspect_locate",
  "rlm_behaviors": ["inspect_locate", "persistent_state", "combine_verify_finish"],
  "behavior_rationale": {
    "inspect_locate": "Concrete task properties that make this behavior useful here.",
    "persistent_state": "...",
    "combine_verify_finish": "..."
  },
  "question": "The natural engineering request, including the answer format.",
  "answer_kind": "patch",
  "answer_format": "unified_diff",
  "context": {"scope": "repository", "files": []},
  "include_failure_log": true,
  "setup_patch": "--- a/...\n+++ b/...\n@@ ...",
  "probe_patch": null,
  "hidden_tests_patch": null,
  "evidence": [{"path": "src/pkg/b.py", "symbol": "src/pkg/b.py::normalize_key", "why": "Where the answer is grounded."}],
  "expected_answer": null,
  "notes": "Anything the verifier should know."
}
```

- `answer_format`: `unified_diff` for patches; `set` for node IDs and
  unordered symbols; `ordered_list` when order matters; `scalar` or `object`
  for values.
- `context.scope`: `repository` (the whole snapshot within size limits) or
  `files` (an explicit list; required for `direct_solve`).
- `expected_answer`: your belief, if you have one. The pipeline never uses
  it as ground truth.

## Acceptance criteria

The pipeline accepts a task only if all of these hold:

1. Every patch applies to the pinned files. A setup defect makes at least one
   and at most a quarter of tests fail, identically on every run.
2. The reference solver, working in the same harness the student uses,
   produces an answer that matches the executable ground truth.
3. A model without access to the repository cannot produce the answer.
4. The reference execution exhibits each claimed behavior.
5. The question is natural, unambiguous and non-trivial. It is not padded,
   does not leak its answer, does not prescribe RLM operations, and is not a
   near-duplicate of another accepted task.
