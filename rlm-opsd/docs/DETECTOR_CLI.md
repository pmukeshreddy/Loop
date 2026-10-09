# Offline detector CLI

The CLI reads existing trajectory JSON, runs static detector analysis, and writes
`behavior.md` and `behavior.csv`. It never executes trajectory code, calls a
model, or fills missing detector thresholds.

```bash
.venv/bin/python -m rlm_opsd.detectors \
  --config tests/fixtures/detectors/fixture-config.yaml \
  --manifest tests/fixtures/detectors/manifest.json \
  --output docs/logs/m4/fixture-report \
  --source-label 'Hand-labelled fixtures; not model results'
```

This command uses manually authored fixtures and fixture-only thresholds. Its
phase names exercise report formatting; its numbers are not model results.
The fixture manifest contains `before` and `teacher` records and deliberately
leaves `after` absent, which the report marks `not run`.

All four named arguments are required. Config, manifest, and output paths are
relative to the working directory. A manifest is a JSON array of records:

```json
[
  {
    "phase": "before",
    "trajectory_path": "logs/task.json",
    "task_success": false,
    "task_metadata": {
      "context_type": "str",
      "context_total_length": 100,
      "context_lengths": []
    }
  }
]
```

Only `phase` and `trajectory_path` are required in each record. Relative trajectory
paths resolve from the manifest directory; absolute paths are accepted. A source
file may appear only once across all phases. `task_success` is an optional
explicit boolean; omission remains unknown. `task_metadata` is an optional
object passed directly to `analyze_trajectory` for legacy logs that lack context
geometry. It contains metadata, never raw context. Unknown record fields are
rejected to catch misspelled labels and metadata keys at the manifest level.

Successful execution prints a JSON object containing the Markdown and CSV paths.
Input and validation failures return a nonzero status before report writes.
Existing reports are refused unless `--overwrite` is supplied, which still
protects unrelated files and input trajectories. See
[report semantics](DETECTOR_REPORTS.md) for aggregation and denominator details.
