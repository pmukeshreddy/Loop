# Teacher manual changelog

## manual_v1 — 2026-10-09

Initial registered version: the supplied `teacher_manual.md`, preserved byte for
byte in `versions/manual_v1.md`. No wording or worked-example answers were added.
`versions.json` pins both the shared student API and the manual snapshot by
SHA-256. The active `teacher_manual.md` must match its registered snapshot.

For a future manual edit, add the next `manual_vN` snapshot, retain previous
snapshots, record the reason here, and update the active registry entry and its
checksum. Version changes identify source text; runtime budget values are
rendered separately. Custom system prompts must use a `custom_...` provenance
label and cannot claim a registered manual version.
