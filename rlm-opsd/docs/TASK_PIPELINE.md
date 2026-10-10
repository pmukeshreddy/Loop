# M2 task pipeline

Run commands from `rlm-opsd/` using the M0/M1 environment. This pipeline is CPU
code and uses a spawn-based process pool on macOS or Linux. It does not start
inference or training. Source contracts are in [VERIFIED_APIS.md](VERIFIED_APIS.md),
and executed results are in [PROGRESS.md](PROGRESS.md).

## Build and verify

```bash
make test-m2
make tasks                         # requires a new or empty data/ directory
make tasks-verify

# Preserve an existing pool by selecting a fresh destination:
make tasks TASK_OUTPUT=data-rebuild
make tasks-verify TASK_OUTPUT=data-rebuild
```

`TASK_CONFIG=configs/tasks.yaml` is the default and can be overridden. `make
tasks` first prepares sources: missing public CSV/query files are downloaded
from exact revision URLs and SHA-256 checked. A corrupt cache fails; it is not
silently accepted. The build then generates, independently verifies, filters,
and atomically writes the candidate pool. It refuses to overwrite a nonempty
output directory.

Individual CLI commands are:

```bash
.venv/bin/python -m rlm_opsd.tasks prepare --config configs/tasks.yaml
.venv/bin/python -m rlm_opsd.tasks build --config configs/tasks.yaml --output data-rebuild
.venv/bin/python -m rlm_opsd.tasks verify --config configs/tasks.yaml --manifest data-rebuild/manifest.jsonl
```

`verify` reloads the serialized context and recomputes each generated answer.
It does not certify benchmark ground truth or held-out coverage. Preparation
and generation may succeed with partial held-out coverage to allow inspection;
release through the train/dev loader requires complete coverage.

## Configuration and task identity

All operational settings are in [configs/tasks.yaml](../configs/tasks.yaml).
They do not define teacher-gate or OPSD-exit thresholds.

| Key | Meaning |
|---|---|
| `seed` | Master seed; each family/bucket/structure/split/instance gets a stable derived seed |
| `workers` | Positive number of worker processes; `1` runs serially |
| `size_buckets` | Target context characters, not tokenizer tokens |
| `structures` | `str` and/or `list` |
| `encodings` | Rotated across eligible cells: `plain`, `jsonl`, `csv`, `logs`, `markdown` |
| `families` | Family names mapped to positive integer weights |
| `splits` | `train` and `dev_behavior`, each with a positive per-cell multiplier |
| `direct_read_max_chars` | Strict upper bound for small-context controls |
| `labels` | Optional fixed classification-intent selection; omit when using `label_count` |
| `family_knobs` | Per-family parameters, each a fixed value, inclusive `{min, max}` range, or `{choices: [...]}` |
| `classification_sources` | Separate train/dev CSV paths, URLs, SHA-256, revisions, partitions, and ambiguity policy |
| `heldout_index` | Destination for reserved queries and source references |
| `heldout_question_sources` | Pinned query-only artifacts; cannot establish full coverage |
| `heldout_snapshots` | Local, checksum-pinned reserved exports, described below |
| `decontamination.ngram_size` | Word n-gram size for query similarity |
| `decontamination.overlap_threshold` | Drop when Jaccard similarity is strictly greater than this value |

The number of tasks per eligible cell is the family weight multiplied by the
split multiplier. Repo QA has `list` structure only and uses Markdown file
envelopes. Small controls use buckets strictly below the direct-read limit.
The other families cover all configured sizes and both structures. Encoding is
rotated, not an extra Cartesian-product axis. Reports include excluded cells
and both the generated and retained grids.

The default train multiplier is `5`, the dev multiplier is `1`, and the
small-context family weight is `3`. Each knob is sampled from a separate RNG
derived from the task seed and knob name. Worker count and YAML key order do
not change the sampled values. Integer ranges include both endpoints; date
ranges sample calendar days inclusively and use quoted ISO date strings.
For example:

```yaml
family_knobs:
  sparse_retrieval:
    needles: {min: 1, max: 8}
  linear_aggregation:
    label_count: {min: 2, max: 8}
    temporal_filter: {choices: [true, false]}
    cutoff_date: {min: '2023-01-01', max: '2023-06-28'}
```

The shipped ranges cover needles `1–8`, hops `2–4`, label counts `2–8`, repo
files `8–64`, and small-context quantity records `4–24`. Both pair relations
and temporal-filter states are sampled. `label_count` selects a seeded subset
from all labels in the split's pinned corpus, without a fixed allowlist. It
must fit the available labels and cannot be combined with explicit `labels`.

Common generator knobs are `target_chars`, `structure`, `encoding`, and
`chunk_chars`. Leave the grid-derived size/structure knobs to the planner when
using `family_knobs`. Records remain whole across list chunks. Target sizes are
minimums, so complete records/file envelopes can exceed the bucket size; exact
character counts are stored in the manifest.

| Family | Additional knobs and behavior |
|---|---|
| `sparse_retrieval` | `needles` from 1–8; exact parcel IDs, shuffled facts and near-ID distractors |
| `multi_hop` | `hops` from 2–4; keyed links, terminal lookup and decoy terminal |
| `linear_aggregation` | `entries` (optional explicit count), `users`, `labels` or `label_count`, `temporal_filter`, `cutoff_date`, `query_type` (`count` or `most_frequent`) |
| `quadratic_pairs` | Dense-task knobs plus `pair_relation` (`both_have_any` or `cover_labels`); unique pairs sorted numerically |
| `repo_qa` | `files` (at least three), `repo_query_type` (`definition`, `callers`, `config`); generated Python repository |
| `small_context_control` | `records` (positive quantity-record count, default `8`), `direct_read_max_chars`; sum the quantities of a named group |

With no explicit `entries`, dense tasks grow using classification entries until
the target size is reached. With an explicit small count, unrelated records can
pad the context. Temporal filtering means dates strictly after `cutoff_date`
(default `2023-03-31` for direct generator calls). With the filter off, all
dates are eligible. Generated dates span January through June 2023, and user
IDs are synthetic. Most-frequent ties use lexical order and empty results
return `NONE`. Small-context `records` counts quantity records, excluding any
unrelated archival filler used to reach the context-size bucket.

Every query type has four wordings, selected by seed using an RNG separate
from context generation and label sampling. Each wording preserves the same
matching, date, tie-breaking and output-order rules.
The verifier parses the serialized records independently; it does not call the
generator or read `task.answer`. Repo verification uses Python ASTs without
executing repository code.

Plain/log/Markdown formats encode structured records with JSON field values.
CSV uses two columns (`record`, JSON object) to preserve heterogeneous record
schemas and multiline text. JSONL uses one JSON object per line. Repo QA uses
`# File: path` followed by a Python fenced block in each list item.

Task identity includes family, resolved knobs, seed and split. Dense-task knobs
also include a fingerprint of the pinned classification corpus. Resolved knobs,
including selected labels, query criteria, `query_variant` and actual entry
counts, remain in the manifest for audit and offline verification. Neither
these criteria nor annotation maps are passed to the model. Regenerate from
the original build configuration or input `TaskSpec`; resolved manifest knobs
are audit output, not a replacement input recipe (`label_count` and its
resolved `labels` are both recorded, but are mutually exclusive as inputs).

## Classification provenance

Dense tasks use BANKING77, attributed in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). The importer validates the
CSV checksum, rejects TREC, and rejects conflicting normalized text labels by
default. The checked-in configuration explicitly uses `ambiguity_policy: drop`:
all rows of an ambiguous text are removed, rather than arbitrarily choosing a
label. Repeated text with the same label is deduplicated. Import reports record
these changes. The context contains utterances without their gold labels;
independent verification joins text to the pinned annotation map offline.

Train uses the upstream train CSV and dev uses its test CSV. These upstream
partitions are not inherently normalized-text disjoint; the actual generated
pool is separately audited in PROGRESS.md. Changing the label selection or pool
size requires checking that property again. This is separate from mandatory
held-out benchmark decontamination.

## Manifest, context and OPSD input

The output directory contains:

- `manifest.jsonl`: all TASKS.md fields, plus `context_sha256` and `source_refs`.
- `contexts/<task_id>.json`: a JSON string or list of strings, stored separately.
- `build-report.json`: config, source import counts, generated/retained grids,
  exclusions, answer-verification count, decontamination and manifest SHA-256.
- `decontamination.json`: rule counts, per-split counts, match reasons and coverage.

`context_path` is relative to the **manifest's parent directory**. Thus the
default row stores `contexts/<id>.json`, resolving to `data/contexts/<id>.json`.
This convention lets a complete pool move together. Context files are ignored
by Git and can be regenerated; the manifest and reports are retained.

```python
from rlm_opsd.tasks.build import load_tasks

rows = load_tasks("data/manifest.jsonl", split="train")
```

The returned iterator requires an explicit split and yields `example_id`, a
query-only `prompt`, and `info` containing the query, context and task metadata.
There is no answer, annotation map, or verification knob in these records. The
M1 harness loads `info.context` into the REPL and constructs metadata for the
root model. This function returns Python records; it does not initialize a
verifiers environment or a training job.

Train/dev loading checks complete held-out coverage and the manifest hash.
Every load checks context shape, character count, content hash, duplicate IDs,
and paths escaping the pool. `inspection_only=True` explicitly allows reading
an uncertified candidate pool for local inspection; it is not a training release.
Eval imports always have `split="eval_heldout"`, and generation/decontamination
reject attempts to use eval tasks as training candidates.

## Reserved benchmark imports and decontamination

The current public query-only import is **incomplete**. Its zero-drop result is
not evidence of no overlap with all benchmark queries/documents. See the
[executed report](../data/decontamination.json) and
[current build log](checks/task-diversity/04-make-tasks.log).

For complete coverage, supply the actual reserved JSON array or JSONL exports
in `heldout_snapshots`. Each entry has `benchmark`, `path`, `sha256`, `revision`,
`license`, and `complete`. These files are read locally and checksum-checked;
the pipeline does not download or invent missing benchmark contexts. A full
snapshot replaces that benchmark's query-only index. Use one combined export
per benchmark.

`complete: true` is an operator declaration that the file contains the entire
reserved evaluation snapshot, including its source documents. It must never be
used for a sample. The loader additionally checks a nonempty matching record
count, revision, and source references for every record; it cannot independently
prove that an operator's selection covers the intended benchmark.

| Benchmark key | Required exported fields / constraints |
|---|---|
| `sniah` | RULER-style `input`, one-element `outputs`; explicit `question` or a recoverable final `What is/are ...?` question. Supply the actual reserved single-needle snapshot and its seed/revision provenance. |
| `browsecomp_plus` | Already-decrypted `query`, `answer`, `gold_docs`, plus `documents`: exactly 1,000 distinct selected `{docid, text}` records, including all gold documents. The document selection must be the reserved 1K-doc evaluation selection. |
| `oolong` | `dataset: trec_coarse`, `context_window_text`, `question`, `answer`, `answer_type`; optional `context_window_id`. Other source subsets are filtered out. Gold-labelled context is never exposed. |
| `oolong_pairs` | Full `question`/`answer` rows (answer is a list), with `context_len` and the matching unlabelled OOLONG `context_record`, including `dataset: trec_coarse` and matching `context_len`. Empty-answer question templates are insufficient. |
| `longbench_v2_codeqa` | `domain: Code Repository Understanding`, `sub_domain: Code repo QA`, `context`, `question`, `choice_A` through `choice_D`, `answer` in A–D. Other domains are filtered out. |

Direct adapters are `adapt_heldout(...)` and `load_heldout_snapshot(...)` in
[heldout.py](../rlm_opsd/tasks/heldout.py). They return reserved `Task` objects;
source preparation retains only queries/source references in the decontamination
index. This keeps benchmark answers out of the generated training manifest.
Adapter tests use clearly identified fixtures; no full benchmark evaluation was
run in M2.

Query normalization uses Unicode NFKC, case-folding, and word tokens. Exact
matches take precedence over near matches. Near matching compares word n-gram
sets using Jaccard overlap; short queries use their full available word width.
Source matching compares `(dataset, item_id)` across revisions, and normalized
content hashes also catch aliases with different dataset IDs. Rule counts may
overlap; `dropped_total` counts each rejected candidate once. The current default
threshold is a configurable data-filter setting, not an evaluation pass/fail
threshold.

After importing complete reserved snapshots, rerun preparation and build into a
fresh output directory so decontamination and the manifest hash are recomputed
together. Do not edit a report's coverage flag to bypass the missing-data guard.
