# M5 teacher gate

The gate compares the pinned initial model generating with x (`before`) and y*
(`teacher`) on the same fixed `dev_behavior` split. Both use the same sampling
settings, task order and per-task seed. Leaf requests use a separate client to
the frozen initial model; it can share the generation endpoint with the root.
These are generation requests, not teacher scoring for OPSD. The revised
[SPEC §6](SPEC.md#6-opsd-training) makes Mode B in-trainer teacher scoring primary.

Run from `rlm-opsd/`:

```bash
make teacher-gate-check
make teacher-gate GATE_CONFIG=configs/gate.yaml GATE_OUTPUT=reports/my-gate-run
```

`teacher-gate-check` sends no requests and writes no report. It checks local
configuration/data, not remote availability, remote weight bytes or GPU capacity.
A ready preflight does not mean the gate passed. `teacher-gate` creates a new
output directory and refuses to overwrite any existing path.

Before a real run, supply:

- A complete decontaminated pool generated through M2, with its manifest and build
  report. The current inspection-only pool is rejected. No inspection bypass is
  exposed by the gate.
- User-selected values in [configs/detectors.yaml](../configs/detectors.yaml) and
  all acceptance criteria in [configs/gate.yaml](../configs/gate.yaml).
- Generation endpoint URLs and served-model aliases for the pinned Qwen3.5-27B
  revision. Both root and frozen clients must use the same initial base weights
  and the pinned chat template/thinking behavior. Endpoint identity is declared
  by the operator; response model aliases are checked, remote weight/template
  bytes are not independently verified.
- If authentication is required, set the named environment variable and put only
  its name in `api_key_var`. For a local unauthenticated server, use null. URLs
  must not embed credentials or query parameters.

No server provisioning or weight download is performed here. Use the existing
[server setup script](../scripts/setup_m0_server.sh) for the pinned environment. GPU execution
and server-side template parity remain deployment checks.

## Settings and acceptance

Paths in `gate.yaml` resolve relative to that file. `root_endpoint` and
`frozen_endpoint` contain `base_url`, `served_model`, `api_key_var`. Timeouts apply
to requests and complete episodes. Requests use no automatic HTTP retries; an
infrastructure failure stops the run with preserved partial evidence. The root
uses the harness token/turn budgets. The manual builder/version and both prompt
variants are the existing M3 implementations.

Each gate criterion names a metric (D1–D18 or `task_tag_match`), a dimension
(`overall`, `family`, `size_bucket`, `domain`), a group, a min/max threshold,
minimum known trajectory count and maximum unknown fraction. `group: "*"`
applies separately to every observed group in that dimension; overall uses
`group: all`. Size-bucket group labels are strings. Threshold comparisons are
inclusive. No criterion is inferred from task correctness.

Only teacher rows determine acceptance; baseline rows are reported alongside.
Missing groups/measurements, insufficient known counts or excessive unknown
fractions are inconclusive. A known criterion failure dominates inconclusive
criteria; a run infrastructure error dominates every criterion result. The gate
cannot pass on partial paired runs. Syntax rate pools failed blocks over known
code blocks, using the M4 aggregation contract; a run with no code does not
silently become a zero syntax-error rate.

The default config includes task-tag and syntax-rate criteria with null
acceptance settings. These intentionally do not run until filled by the user.
Add explicit family/bucket/domain criteria to enforce group-specific requirements.
A failed teacher-policy run is evidence for a versioned manual revision and a
new gate run; M5 does not rewrite the manual based on fixtures or missing data.

Exit codes: 0 passed (or locally ready for `--check`), 1 infrastructure/error,
2 not run due to missing prerequisites, 3 threshold failure, 4 inconclusive.

## Evidence files

- `run.json`: settings without secret values, timestamps, input/config hashes,
  model revision, template/thinking/manual metadata, fixed task IDs and grid.
- `requests.jsonl`: root/frozen request outcomes, source trajectory, response
  model/ID, optional usage, token-ID availability, timing and exception type.
  Provider exception messages are excluded before they can reach REPL/model
  observations or trajectory logs.
- `trajectories/before/*.json` and `trajectories/teacher/*.json`: actual persistent
  harness logs. Original token IDs are retained when supplied; missing IDs are
  not reconstructed. Failed episodes keep their trace.
- `records.jsonl`: M4 analyses and relative trajectory paths, without answers or
  invented task-success labels.
- `behavior.md`, `behavior.csv`: all detectors, task-tag matching, syntax and
  subcall statistics by family, bucket and domain. `after` remains not run.
- `gate.json`, `gate.md`: every configured acceptance check, links and final status.

Budget/protocol failures are measured model behavior; worker transport errors,
endpoint failures and cleanup/analysis failures are run errors. Cleanup is
attempted independently for both clients. Recursive child worker failures also
invalidate the run and link their raw trajectories, even if a parent recovered
and returned a valid finish. Child budget hits remain measured behavior.
If the output filesystem itself fails,
artifact finalization can also fail; previously saved raw trajectories remain
available. No training stage is started by a passing gate.

Tests use hand-authored task pools and a local HTTP fixture server plus the real
REPL harness. Their synthetic response/report labels explicitly say they are not
model results. `make test-m5` runs those contracts. The real gate acceptance
criterion is not satisfied by these tests; see [PROGRESS](PROGRESS.md) for what
was actually run.
