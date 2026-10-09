# Hand-labelled offline detector fixtures

These JSON files are manually authored fixtures, not model runs. The config
contains fixture-only detector thresholds, not user operational thresholds.
The explicit `task_success: false` is a fixture label, not a correctness score.

- `before.json` prints the entire context first: D1 and D2 fail.
- `teacher.json` probes first, reads a small slice, and finishes with a computed
  variable: D1, D2, D14, and D15 pass. Its supplied metadata makes the ten-character
  slice cover one tenth of the hundred-character context (D18 = 0.1).
- `manifest.json` supplies geometry for the legacy-shaped teacher fixture and
  deliberately supplies no `after` trajectory. That phase must remain `not run`.

The phase names exercise the three-way report format; they do not represent
base-model, teacher-model, or checkpoint measurements.
