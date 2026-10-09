# TASKS: task pool for OPSD (and later GRPO)

## 1. Manifest schema (`data/manifest.jsonl`, one task per line)

```json
{
  "task_id": "agg-000417",
  "family": "linear_aggregation",
  "domain": "long_context",
  "split": "train | dev_behavior | eval_heldout",
  "context_path": "data/contexts/agg-000417.json",
  "context_format": "str | list",
  "context_chars": 2400000,
  "query": "Which label appears most often among entries dated after March 2023?",
  "answer": "location",
  "answer_type": "exact | list_f1 | multiple_choice | numeric",
  "tags": ["large_context", "dense", "needs_subcalls", "aggregate_in_code"],
  "knobs": {"entries": 4000, "label_set": "coarse6", "temporal_filter": true},
  "seed": 417,
  "source": "dataset name + license"
}
```

- Store contexts as files and load them into the REPL at episode reset.
- OPSD does not use `answer`. It is kept for monitoring and for GRPO rewards.

## 2. Families

| Family | Description | Knobs | Tags (expected behavior) |
|---|---|---|---|
| `sparse_retrieval` | Needles (facts, numbers, phrases) inserted into unrelated text | Haystack size, 1–8 needles, needle format, near-duplicate distractors | `sparse`, `code_search`, `windowed_read`, `verify_hit` |
| `multi_hop` | A document collection where the answer requires following names or IDs across 2–4 documents | Number of docs, hops, distractor docs | `sparse`, `code_search`, `chained_search`, `verify_hit` |
| `linear_aggregation` | OOLONG-style: entries with user ID, date, and text taken from classification datasets. Labels are not given and must be inferred from meaning. Questions ask for counts, most-frequent label, or temporal filters. | Entries, label set, temporal conditions | `dense`, `needs_subcalls`, `subcalls_in_loop`, `buffer_store`, `aggregate_in_code` |
| `quadratic_pairs` | List all pairs of user IDs that satisfy label conditions | Entries, conditions | `dense`, `needs_subcalls`, `aggregate_in_code`, `output_in_variable` |
| `repo_qa` | A code repository as a list of file strings; questions about definitions, call sites, or config values | Repo size, question type | `code_search`, `windowed_read`, `subcall_on_matches` |
| `small_context_control` | Contexts small enough to read directly | Size below the direct-read threshold | `small_context` (direct reading allowed) |

**Exclusions for `linear_aggregation`:** do not use TREC as a source dataset, because the held-out OOLONG `trec_coarse` split is built from it. Use other classification datasets and record each source.

**GRPO-only family (added after OPSD exit):** `swe_rlm`, which is SWE tasks inside the RLM harness with repo tools as REPL helpers. Sources: an R2E-Gym subset, or SWE-smith-style generated bugs.

## 3. Size buckets and structure

- **Context size buckets** (configurable in `configs/tasks.yaml`): 8K, 32K, 128K, 512K, 2M, 8M chars.
- **Structure:** `str` versus `list[str]`, and plain text, JSON lines, CSV, logs, or Markdown sections.
- **Balance** the families × size buckets × structure grid. Report the actual counts in `PROGRESS.md`.

## 4. Splits

| Split | Use |
|---|---|
| `train` | OPSD rollouts (mixed pool, family ratios in config) |
| `dev_behavior` | Teacher gate and periodic behavior eval. Fixed and small, with every family × bucket represented. |
| `eval_heldout` | The paper's benchmarks only: S-NIAH, BrowseComp-Plus (1K docs), OOLONG `trec_coarse`, OOLONG-Pairs, LongBench-v2 CodeQA. Never trained on. |

## 5. Decontamination (mandatory)

- Drop any train or dev task whose query exactly or near-exactly matches a held-out query (normalized text, n-gram overlap above a threshold set in config).
- Drop any train or dev task that shares source documents or entries with held-out sets.
- Write a decontamination report with the counts dropped by rule.

## 6. Generators

- Each generator is deterministic given `(family, knobs, seed)`.
- Each generator ships a verifier that recomputes the answer from the context, used in tests on small instances.
- Generation runs in parallel. Ray is optional; a process pool is fine.
- Log every generated task's knobs and source.
