# Step 3 — Synthetic DeepSWE data

Goal: a large set of executable software-engineering tasks. Each one has a real repository, a pinned commit, an instruction, and a verifier that returns pass or fail.

This is the training distribution for step 4. It is not the Datacurve DeepSWE benchmark. The 113 public tasks, and the 8 tasks used in step 1, stay held out.

## Shape of one instance

Match the shape Agentica DeepSWE trained on: a repo in a container, a natural-language task, and tests.

```text
instance_id
repo_url
base_commit
instruction.md          # what the agent sees
environment/            # Dockerfile, or a prebuilt image id
tests/                  # verifier only. Applied at grade time, not visible to the agent
  test.patch
  test.sh
reference.patch         # used to check the task is solvable. Never shown to the policy
timeout_sec
```

Reward, computed by the grader, not stored as a label the agent can read:

- `1` if the submitted patch passes the new tests and the selected existing tests still pass
- `0` otherwise, including timeout and no submission

The verifier asserts observable behavior. It should accept any implementation that does the requested thing. A test that imports a private helper the instruction never named is a bad instance. Drop it.

## How to build one

1. Pick a permissive, actively maintained public repo. Pin a commit.
2. Write an original task against that tree. Do not copy a merged pull request, its tests, or its discussion. Those are already in pretraining data.
3. Write the tests from the instruction. Run them three times on the base commit. They must fail every time.
4. Write `reference.patch`. Apply it in a clean container. The tests must pass every time, and the existing regression tests must still pass.
5. If the result flips across the three runs, the instance is flaky. Drop it.
6. Ship the container as a shallow clone at `base_commit`. No gold commit in the git history.

Languages: Python, TypeScript, JavaScript, Go, Rust. Spread repos. Do not let one repository dominate the set.

Scale: thousands of instances, on the order of the 4,500 R2E-Gym tasks DeepSWE trained on. Quality filters above matter more than hitting that count.

## Split

| Split | Used by | Source |
|---|---|---|
| `eval` | Step 1, and the final report | Datacurve DeepSWE 113. Untouched. |
| `trace` | Step 2 privileged traces | Small train-only pool. Already built before this step. |
| `train` | Step 4 GRPO | This file's output. |
| `dev` | GRPO hyperparameter checks | A few hundred instances held out of `train`. |

## Done when

A script can load an instance, start its container at `base_commit`, apply a patch, run `tests/test.sh`, and return 0 or 1. The reference patch scores 1. The empty patch scores 0. No instance id overlaps the Datacurve 113.

## Do not

- Do not train on Datacurve tasks.
- Do not grade with an LLM judge. The reward is the executable verifier.
- Do not put the reference patch or the test patch in the prompt.
