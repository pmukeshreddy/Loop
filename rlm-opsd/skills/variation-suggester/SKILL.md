---
name: variation-suggester
description: Propose substantive variations of an accepted, verified DeepSWE task that change its constraints, dependencies, failure conditions or relevant evidence, so the variation needs a different investigation and has a different verified answer. Use after a seed task is accepted.
---

# Variation suggester

You receive one accepted task: its question, intended RLM behaviors, the
verified answer, the ground-truth evidence and the repository files it
involves. You propose variations that are new problems, not new wordings.

## What counts as substantive

A variation must change *what has to be found* or *how it has to be found*.
Its verified answer, or the evidence path to that answer, must differ from
the original. Useful axes:

| change_type | Examples |
|---|---|
| `constraint` | A different input, option, flag or configuration that routes behavior through another branch. A stricter or looser requirement on the deliverable. |
| `dependency` | The same symptom reached through another caller, subclass, registry entry or layer. A change aimed at a different module in the same chain. |
| `failure_condition` | A different defect that produces a similar visible symptom. Two interacting defects. A failure that only appears in one code path. |
| `evidence` | A user report instead of a CI log. Evidence spread across docs and tests instead of a traceback. A focused context instead of the whole repository, when a direct read is then the right strategy (or the reverse). |
| `deliverable` | Diagnosis turned into repair, impact prediction turned into a fix, a fix turned into an implementation with acceptance tests. |

Variations may move the task toward different RLM behaviors. For example,
widening the evidence can make selective sub-calls useful, and narrowing the
context to one small module can make a direct read correct. State the shift.

## Reject your own idea if

- it asks for the same investigation or fix as one of the
  `other_tasks_in_repository` listed with the task;
- it only paraphrases the question or renames identifiers;
- the verified answer would stay the same;
- it repeats the original's answer pattern (the same symbol, the same
  tests, the same fix) with cosmetic differences;
- it can be answered without examining the repository;
- it becomes a trivial lookup;
- it needs padding to look different;
- it forces sub-calls or recursion where a competent engineer would not use
  them, or uses call counts as the point of the task.

## Output

Return one fenced `json` block:

```json
{
  "suggestions": [
    {
      "change_type": "failure_condition",
      "description": "Concrete description of the new problem, with the files and symbols involved.",
      "why_substantive": "How the investigation and the verified answer change.",
      "expected_answer_change": "What the new answer depends on.",
      "behavior_shift": "Which behaviors the variation exercises, and why they are useful there."
    }
  ]
}
```

Propose exactly the number of suggestions requested, each on a different
axis when possible.

## Acceptance criteria

1. Each suggestion names real files and symbols from the material shown.
2. Each suggestion changes the ground truth or the evidence path.
3. No suggestion would be rejected by the list above.
