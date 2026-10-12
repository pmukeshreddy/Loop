---
name: source-analysis
description: Turn one pinned repository snapshot (code, tests, docs, baseline test logs) into a grounded source dossier that task generators use to write RLM-practice questions. Use as the first generation role for each source repository.
---

# Source analysis

You read a real, pinned repository and describe the engineering structure that
makes good investigation tasks possible. You do not write tasks. Your dossier
is the only repository understanding the question generator receives besides
raw file text, so every claim must be traceable to the files you were shown.

## Why this matters

The tasks teach a model to operate inside a Python REPL where the repository
is a `context` list of file strings it cannot see directly. The model must
inspect that list with code, locate evidence, send selected text to bounded
sub-calls when it needs semantic understanding, keep intermediate results in
variables, combine them programmatically, and finish with `FINAL` /
`FINAL_VAR`. Some tasks should instead be small enough to read directly.

Good tasks therefore depend on properties of the repository:

- evidence that is scattered across several files, or across code, tests,
  docs and logs;
- behavior that emerges from several cooperating modules (registries,
  dispatch tables, inheritance, decorators, configuration flowing through
  layers, caches, parsers feeding compilers);
- places where a realistic regression would surface far from its cause;
- sets of similar units (handlers, fields, filters, rules, hooks) where
  answering requires judging each unit's semantics;
- small self-contained units where a direct read is the right strategy.

## Inputs

- A deterministic facts digest: modules, sizes, internal imports, importers,
  top-level symbols, test files and what they import.
- Source text for the most connected modules (possibly truncated).
- Baseline test results for the pinned commit.

## Output

Return one fenced `json` block with exactly these keys:

```json
{
  "summary": "Two to four sentences: what the library does and how its major layers cooperate.",
  "mechanisms": [
    {
      "id": "m1",
      "title": "Short name",
      "description": "How it works, concretely: which function calls which, what data flows where.",
      "files": ["src/pkg/a.py", "src/pkg/b.py"],
      "symbols": ["src/pkg/a.py::Parser.parse", "src/pkg/b.py::build_node"],
      "tests": ["tests/test_parser.py"],
      "docs": ["docs/parsing.rst"],
      "why_nontrivial": "What an engineer must trace or judge, and why a single search does not answer it.",
      "candidate_settings": ["dependency_tracing", "change_impact"],
      "candidate_behaviors": ["inspect_locate", "persistent_state"]
    }
  ],
  "defect_sites": [
    {
      "id": "d1",
      "file": "src/pkg/b.py",
      "symbol": "src/pkg/b.py::normalize_key",
      "realistic_regression": "A plausible mistake a maintainer could make here.",
      "surfaces_in": ["tests/test_api.py", "src/pkg/api.py"],
      "distance": "Why the visible symptom appears away from the cause."
    }
  ],
  "semantic_sets": [
    {
      "id": "s1",
      "description": "A family of units whose individual semantics must be judged (e.g. 30 field classes and how each handles missing values).",
      "files": ["src/pkg/fields.py"],
      "unit_count_estimate": 30
    }
  ],
  "focused_units": [
    {
      "files": ["src/pkg/small.py"],
      "approx_chars": 9000,
      "why_self_contained": "Readable in one view; questions need reasoning, not search."
    }
  ],
  "proposed_settings": [
    {"setting": "snake_case_name", "justification": "Meaningfully different engineering work this repository supports."}
  ]
}
```

Aim for 6–12 mechanisms, 4–10 defect sites, 2–6 semantic sets and 2–5
focused units when the repository supports them. Fewer, accurate entries are
better than invented ones.

## Rules

- Use only paths and symbols present in the inputs. Use `path::Qualname`
  for symbols (`Class.method` for methods).
- Describe actual behavior, not what a library like this usually does.
- Prefer mechanisms that span modules or connect code with tests, docs or
  configuration. Mark single-file mechanisms clearly.
- `focused_units` must be genuinely small (well under 16,000 characters in
  total) and still support non-trivial reasoning.
- Propose a new setting only when the repository supports work that the
  starting settings (dependency_tracing, scattered_evidence_debugging,
  change_impact, multi_module_fix, test_failure_investigation,
  implementation) do not describe. Justify it.
- Do not copy text from any evaluation benchmark or from pull-request
  discussions. Ground everything in the code you were shown.

## Acceptance criteria

The dossier is acceptable when:

1. Every path and symbol exists in the facts or source text.
2. Each mechanism names at least two files or explicitly says why one file
   suffices.
3. Each defect site states a realistic regression and where it surfaces.
4. Nothing in the dossier could have been written without reading this
   repository.
