# M1 harness

Run from `rlm-opsd/` with the M0 inspection environment:

```bash
uv pip install --python .venv/bin/python -r requirements-m1.txt
make test
```

`make test-m1` runs just the harness suite. On the prepared Linux server use
`make test PYTHON=.venv-server/bin/python`. Server installation, GPU inference,
and training have not been run here. Tests use actual Python subprocesses,
the pinned verifiers rollout loop, and a local HTTP fixture for the frozen
endpoint. No test requires a model download or API credential.

## Environment entry point

`rlm_opsd.load_environment(**kwargs)` returns `RLMOpsdEnv`, a subclass of the
pinned `rlm_train.RLMTrainEnv`. It uses that adapter's worker and transport
contracts; it does not use verifiers' built-in `RLMEnv`. The upstream packages
are unmodified. Run with the project root on `PYTHONPATH` when importing from
another working directory.

Example configuration for an already running frozen model server (not executed
against a real model in M1):

```python
import verifiers as vf

env = vf.load_environment(
    "rlm_opsd",
    dataset=dataset,  # caller-provided datasets.Dataset; see TASK_PIPELINE.md
    config="configs/harness.yaml",
    frozen_client={
        "api_base_url": "http://127.0.0.1:8001/v1",
        "api_key_var": "FROZEN_MODEL_API_KEY",
        "max_retries": 0,
        "timeout": 60,
    },
    frozen_model="initial-weights",
    log_dir="trajectories",
)
```

The caller supplies the root client/model to the normal verifiers rollout API.
The frozen client can be a `vf.Client`, `ClientConfig`, or a configuration dict.
An externally supplied client remains owned by its caller; the environment
closes clients it creates at teardown. The same client object cannot be both
root and frozen. **The server operator must ensure `frozen_model` serves the
initial weights and does not receive student weight updates.** A client name
cannot verify weight immutability. Subcalls never fall back to the root client.

Each row's `info` must contain `task_id`, `family`, `domain`, `tags`, `query`,
and `context` (`str` or `list[str]`). Put the long context there, not in a model
message. The wrapper constructs the initial user message from `query` only;
metadata is rendered in the shared system API block. `prefix_chars` defaults to zero; an explicitly configured prefix
is the sole initial context excerpt. For lists, lengths count each chunk and
the prefix concatenates chunk starts in order without inserting separators.

M3 now supplies the default registered student/teacher prompts. Select
`prompt_variant` (`student` or `teacher`); `manual_version` defaults to the active
registered manual. `prompt_builder` can select a verified source bundle and
`prompt_config` selects the pinned chat/thinking settings. An explicit
`system_prompt` override requires a `custom_...` version label. See
[PROMPTS.md](PROMPTS.md) for rendering, versioning and token alignment.
The wrapper preserves provider reasoning fields in subsequent root requests;
only assistant content is parsed as executable code or a finish command.

## Limits and protocol

[configs/harness.yaml](../configs/harness.yaml) declares every M1 budget.
`max_tokens_per_turn` caps the request sent to the root server, including thinking
tokens; it does not retokenize or silently clip the response. Server-side token
limit compliance is an inference-server responsibility. Root decoding settings
other than this cap remain under the caller's control.

REPL variables, including function globals and assignments before an exception,
persist. All Markdown fenced regions are excluded from finish detection.
Only `repl` fences execute, in order, up to the first external finish command.
`FINAL_VAR(name)` accepts an identifier, not an expression. Missing variables
produce a protocol-error observation and `finish_error`, allowing another turn
if budget remains. Text and code after the finish command are retained in
`ignored_after_finish` and never executed. The upstream answer-dictionary
completion mechanism is disabled. A valid finish on the last allowed turn wins
over the turn cap; a nonfinishing last turn still executes before termination.

`stdout_raw_chars` counts **combined stdout and stderr**, in write order,
including tracebacks. `stderr_raw_chars` is its stderr subset. The worker keeps
only a bounded prefix while counting all characters. `stdout_truncated` stores
that prefix and, when needed, a notice containing the full length. The cap is
per assistant turn across all code blocks; the notice is additional to the cap.
Protocol and sandbox errors are separate observation suffixes and trace fields.

`max_subcall_chars` applies to each prompt (Unicode characters). Oversized calls
are logged and rejected without consuming `max_subcalls`. Accepted attempts,
including server failures/timeouts, consume that budget before any await.
Singles and batches share an asynchronous concurrency semaphore. Calls record
zero-based root turn index, depth, prompt/output character counts, elapsed time
(including queueing), and errors. Budgets span the whole episode.

Recursion is absent from the REPL by default. To expose `rlm_query(prompt)`, set
`enable_recursion: true` and `max_depth` to at least two. It starts a child REPL
whose context is the supplied prompt and whose root uses the frozen client.
Child root requests and leaves share the parent's subcall budget/concurrency;
the child has its own turn cap and JSON trace. Nested calls at the depth cap
return a logged error. There is no alias from `rlm_query` to an ordinary leaf.

## Resource containment and logs

The worker runs in its own process group and temporary working directory, with
an environment allowlist that excludes parent API keys. Wall time applies to
each execution or final-variable resolution, including time waiting on subcalls.
The parent samples worker/descendant RSS and CPU every 20 ms; memory can briefly
exceed its cap between samples. CPU is cumulative after worker initialization.
Process groups are killed on limit violations, cancellation, and cleanup.
Linux additionally sets `RLIMIT_AS` to initial virtual size plus the configured
memory allowance; `RLIMIT_CPU` supplies a whole-second kernel backstop. The
precise configured resident-memory cap is enforced by the parent watchdog.

This is resource containment, **not a hostile-code security sandbox**. Imports,
filesystem access and network access remain available as in the reference
worker. Very short-lived/reparented descendants can evade sampled accounting;
processes that deliberately escape the group require stronger OS isolation.
Use an appropriately isolated server/container for untrusted workloads. The
Linux-specific address-space backstop has not been executed on this Mac.

Every episode writes one validated JSON file at close, using an unpredictable
episode ID as its filename, an atomic replacement, and no task ID as a path.
The original task ID is retained inside the file. Success, caps, worker failures,
and cancellation are recorded. The full original completion token IDs are copied
from the provider response, without retokenization; verifiers may independently
clip its training representation at `max_seq_len`. `state['opsd_trajectory_path']`
locates the trace after rollout cleanup.
