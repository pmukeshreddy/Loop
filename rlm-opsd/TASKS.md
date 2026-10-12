# TASKS: DeepSWE task pool for OPSD (and later GRPO)

The OPSD phase teaches RLM operation. Tasks are therefore organized by the RLM
behavior they give practice in. Real DeepSWE-style repository work (code,
dependencies, tests, documentation, execution logs) is the domain and source
material. Debugging, dependency tracing, impact analysis and implementation
are the settings in which the behaviors are practiced.

Generation follows AgentInstruct (Mitra et al., arXiv:2407.03502): content
transformation of real sources, seed instruction generation from a taxonomy,
and suggester/editor refinement, each by a role with its own instructions in
`skills/<role>/SKILL.md`. Operating details: `docs/TASK_PIPELINE.md`.

## 1. Behaviors (task family = primary behavior)

| Family | Behavior | Task properties that make it useful |
|---|---|---|
| `inspect_locate` | Inspect context and locate relevant evidence using code. | Large repository context; evidence is a small, scattered fraction reached by following names, registrations and test references. |
| `chunked_subcalls` | Select and chunk relevant context for bounded semantic sub-calls. | Semantic judgment over more selected text than fits in one read (many similar units, long docs or logs). |
| `recursive_decomposition` | Decompose investigations into useful recursive calls. | Independent sub-investigations (per failing test, caller, module) whose findings are combined. |
| `persistent_state` | Maintain and reuse intermediate results in persistent REPL variables. | Dependent steps reuse indexes, candidate lists, extracted facts or file text being edited. |
| `combine_verify_finish` | Combine and check findings programmatically, then finish with `FINAL` / `FINAL_VAR`. | Aggregate deliverables (node-ID sets, symbol lists, patches built from exact file text) that should be checked in code. |
| `direct_solve` | Recognize when a task can be solved directly without delegation. | Focused context under `direct_read_max_chars`; still needs real reasoning. |

A task may combine behaviors. The generator records the *intended* behaviors
and a rationale for each. The pipeline then checks the reference execution and
releases only the behaviors it actually exhibited (§4). A task whose primary
behavior was not exhibited is rejected. Questions never tell the solver which
operations to use, and call counts are never a success criterion.

## 2. Settings and answers

Starting settings: `dependency_tracing`, `scattered_evidence_debugging`,
`change_impact`, `multi_module_fix`, `test_failure_investigation`,
`implementation`. The source analyst may add a setting when a repository
supports meaningfully different work, and must justify it.

| answer_type | Executable ground truth |
|---|---|
| `patch` | Defect (`setup_patch`) or acceptance tests (`hidden_tests_patch`). Fail-to-pass tests fail on every run before the fix and pass after it. Pass-to-pass tests stay green. Test files may not be edited. |
| `test_ids` | `probe_patch` implements the described change; tests that newly fail on every run are the answer. Parametrized cases are compared per test function. |
| `symbols` | With a defect: the functions the defect changed, from AST spans. Otherwise: an independent oracle program executes the repository. |
| `value` | An independent oracle program imports and runs the repository code. |

## 3. Manifest schema (`data/manifest.jsonl`, one task per line)

```json
{
  "task_id": "pallets-click-r02-03",
  "split": "train | dev_behavior",
  "family": "inspect_locate",
  "rlm_behaviors": ["inspect_locate", "persistent_state"],
  "behavior_rationale": {"inspect_locate": "...", "persistent_state": "..."},
  "setting": "scattered_evidence_debugging",
  "domain": "deepswe",
  "tags": ["large_context", "sparse", "output_in_variable"],
  "query": "Natural engineering request, including the answer format.",
  "context_path": "contexts/<sha256>.json",
  "context_format": "list",
  "context_chars": 412345,
  "context_sha256": "...",
  "size_bucket": 1048576,
  "answer": "verified reference answer or unified diff",
  "answer_type": "patch | test_ids | symbols | value",
  "answer_format": "unified_diff | set | ordered_list | scalar | object",
  "repo": {"name": "pallets/click", "url": "...", "ref": "8.5.0", "commit": "<40 hex>", "license": "BSD-3-Clause"},
  "source_refs": [{"dataset": "github", "item_id": "pallets/click", "revision": "repository", "sha256": "..."}],
  "parent_id": "null, or the seed task a variation came from",
  "variation": "null, or the accepted suggestion (change_type, rationale)",
  "practice": {"intended": [], "results": {"<behavior>": {"established": true, "evidence": "..."}}, "facts": {}},
  "verification": {"method": "tests | impact | defect_symbols | oracle", "fail_to_pass": [], "impact_tests": []},
  "reference_path": "references/<task_id>",
  "provenance": {"model": "...", "skills": {"<role>": "<sha256>"}, "tree_sha256": "...", "documents": []}
}
```

- The context is a list of strings: one per repository file (`# File: <path>`),
  then execution logs (`# Log: <title>`) captured from real test runs.
- `references/<task_id>/` holds the reference answer, the patches, the oracle
  program, the reference RLM trajectory, test logs and the verifier review.
- `tags` are derived from the established behaviors and context size, so the
  detector tag requirements (DETECTORS.md §3) match demonstrated behavior.

## 4. Acceptance

A candidate is released only if all of these hold. Each failure is logged with
a reason code in the work directory's `rejections.jsonl`.

1. Valid spec: consistent behaviors, rationales, answer kind and artifacts.
2. The question does not prescribe RLM operations or leak its answer.
3. Patches apply. Defects break at least one and at most a quarter of passing
   tests, identically on every stability run. Impact sets stay within the
   configured size range.
4. The reference solver, running in the student's RLM harness, produces an
   answer that matches the executable ground truth.
5. A model without repository access cannot produce the answer.
6. The reference execution exhibits the primary intended behavior.
7. An independent reviewer accepts it as natural, unambiguous, non-trivial,
   unpadded and repository-dependent, and (for variations) substantive.
8. The question is not a near-duplicate, and the answer is not a repeat, of
   another accepted task from the same repository. A variation's verified
   answer must differ from its parent's.
9. At release, the executable ground truth reproduces on a fresh run.

## 5. Splits

| Split | Use |
|---|---|
| `train` | OPSD rollouts. |
| `dev_behavior` | Teacher gate and periodic behavior evaluation. Must contain every family. |
| `eval_heldout` | Never generated. The paper's long-context benchmarks, plus DeepSWE-113 for step 1 and final reports. |

Repositories are assigned to `train` or `dev_behavior` in `prepare`, before
any generation, using a size-stratified seeded draw. Every task and variation
inherits its repository's split, so related tasks cannot cross splits.

## 6. Decontamination (mandatory)

- Repositories that are DeepSWE-113 upstreams cannot be configured as sources.
- Release drops any task whose query exactly or near-exactly matches a held-out
  query, including DeepSWE instructions, or that shares a source repository
  with a held-out record.
- The training loader refuses train/dev release until every reserved
  benchmark has complete coverage (`docs/TASK_PIPELINE.md`).

## 7. OPSD semantics

The loader yields only the task ID, family, domain, tags, query and context.
Reference answers, patches, trajectories and rationales never enter the
student prompt, the task-independent teacher manual, or any loss. No SFT stage
uses the reference trajectories, and OPSD adds no correctness reward.
