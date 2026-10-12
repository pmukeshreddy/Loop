---
name: variation-editor
description: Implement one variation suggestion as a complete, executable DeepSWE task specification (question, behaviors with rationale, answer kind, and new defect, probe or hidden-test patches written against the real files). Use for each accepted variation suggestion.
---

# Variation editor

You turn one suggestion into a full task. The result must be as complete
and verifiable as a seed task from the question generator. It is then
materialized, re-solved by the reference solver in the real harness, and
independently verified, like any other task.

## Requirements

- Follow every rule in the question-generation skill (provided below this
  skill): natural wording, an exact answer format, no answer leakage, no
  prescribed RLM operations, no padding, executable ground truth, and
  patches whose context lines are copied exactly from the files shown.
- Write new artifacts. If the suggestion changes the failure condition,
  write a new `setup_patch`. If it changes the planned change, write a new
  `probe_patch`. Never reuse the original task's patch unchanged when the
  suggestion depends on a different defect or change.
- Write the question fresh. Do not copy the original's sentence structure
  with names swapped.
- Re-derive `rlm_behaviors` and `behavior_rationale` from the new task's
  properties. Do not copy them forward. If the variation now suits a direct
  read, say so and use a focused `files` context under 16,000 characters.
- The verified answer must differ from the original's. If your
  implementation would produce the same answer, change the implementation
  or return an empty task list.

## Output

Return one fenced `json` block: `{"tasks": [ <one task object> ]}`, using the
same task schema as the question generator. Return `{"tasks": []}` if the
suggestion cannot be implemented as a verifiable, substantive task.
