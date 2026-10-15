# M3 prompts and token alignment

The user selected `Qwen/Qwen3.5-27B`. Its tokenizer and chat template are pinned
in [configs/prompts.yaml](../configs/prompts.yaml). The prompt module builds
student/teacher prefixes and preserves aligned token sequences for training.
Its local verification covers rendering and token alignment; executed checks
are recorded in [PROGRESS.md](PROGRESS.md).

## Text construction

```python
from rlm_opsd.harness import HarnessConfig
from rlm_opsd.prompts import PromptBuilder

pair = PromptBuilder.load().build(
    query="Find the requested record.",
    context=context,                     # str or list[str], retained in the REPL
    config=HarnessConfig.from_yaml("configs/harness.yaml"),
)
student_messages = pair.messages("student")
teacher_messages = pair.messages("teacher")
```

The student system is the rendered `prompts/student_system.md`. The teacher
system is that **exact string**, followed by `"\n\n"` and the rendered manual.
Both user messages contain the query unchanged. Only their system content differs.
The default harness now uses these builders, replacing M1's temporary API string
and query-plus-metadata user message. Metadata is in the shared system API block.

The privileged manual addition is task-independent: only operational limits are
substituted into it. The complete system also contains the shared API's permitted
context metadata, and the user message contains the query, as SPEC §3 requires.
Neither builder accepts an answer or a task-info dictionary. The harness selects
only query/context from task info, even if the caller includes an answer field.
Fixed illustrative queries/code in the supplied manual are retained; no actual
task answer is injected.

`render_named` replaces only the eight SPEC placeholder names in one pass.
JSON objects, dictionaries, regex quantifiers and f-string braces remain literal.
Missing values for recognized template placeholders fail. Replacement text is
never recursively interpreted: a context prefix containing `{max_turns}` stays
literal. Consequently, the no-unreplaced-placeholder test checks the template
with ordinary data; arbitrary input text may itself legitimately contain braces.

`context_prefix` uses the M1 metadata helper and the configured character cap;
the default cap is zero. List contexts produce the exact chunk-count/length
description. `subcall_chunk_chars` is the configured chunk size; when omitted
with a custom sub-call limit, its default is half that limit (rounded down, at
least one character). Explicit values must be positive and no larger than the
limit. The default config leaves room for the instructions accompanying chunks.

## Manual source identity

[prompts/versions.json](../prompts/versions.json) registers `manual_v1` and the
student API SHA-256. The immutable
[manual snapshot](../prompts/versions/manual_v1.md) matches the originally supplied
manual byte for byte. Loading verifies the student file, the selected archived
manual, and the active `teacher_manual.md` when selecting the active version.
An unregistered version or changed bytes fail before prompting.

The [changelog](../prompts/CHANGELOG.md) describes future version bumps. Select an
older registered manual with `PromptBuilder.load(manual_version="manual_vN")`.
Episodes record the selected version, including recursive episodes. New default
logs use `manual_v1`; historical M1 logs retain their original `v1` value.

An explicit `system_prompt=` override requires `manual_version="custom_..."`
and cannot be combined with a prompt builder. Its metadata is appended to the
system content and the user message remains query-only. Such a custom override
is not the registered x/y* pair and must not be mixed into a comparison claiming
to use the supplied manual.

## Pinned chat prefixes

```bash
make test-m3           # offline BPE fixtures and real subprocess/HTTP integration
make prompts-prepare  # download missing tokenizer JSON files, verify SHA-256
make prompts-check    # real pinned Qwen tokenizer, thinking on and off
```

The default local environment already includes the required tokenizer libraries
from M0. No new dependency or weight download is needed. A fresh checkout needs
`prompts-prepare` before the real-tokenizer smoke check. Existing corrupt files
fail verification instead of being silently used. The vendored template is also
checksum-checked and is covered by [QWEN_LICENSE](../prompts/QWEN_LICENSE).

```python
from rlm_opsd.prompts import ChatRenderer, PromptConfig, build_teacher_sequence

renderer = ChatRenderer(PromptConfig.from_yaml("configs/prompts.yaml"))
prefixes = renderer.prefixes(pair)

# student_ids are the ORIGINAL recorded S_prefix + all rollout suffix token IDs.
teacher_ids = build_teacher_sequence(
    student_ids,
    student_prefix=prefixes.student_ids,
    teacher_prefix=prefixes.teacher_ids,
)
assert teacher_ids[len(prefixes.teacher_ids):] == tuple(student_ids[len(prefixes.student_ids):])
```

The alignment helper accepts lists or tuples, validates the exact student prefix, and
returns a tuple. It rejects empty prefixes and negative/noninteger IDs. It has no
tokenizer/text input and does not decode or re-tokenize any suffix. Original
assistant, observation, role-marker and subsequent-turn IDs are copied verbatim.
An empty suffix is allowed. This helper does not invent observation token IDs
from the M1 JSON log; the full recorded token sequence is a caller requirement.

Both prefixes use the same tokenizer instance, explicit `chat_template`,
`enable_thinking`, and `add_generation_prompt=True`, with truncation and padding
disabled. The pinned upstream template trims message-edge whitespace. Thinking
on ends the generation prefix with `<think>\n`; thinking off includes an empty
thinking block. Neither mode changes the copied suffix.

`PromptConfig` has these exact keys: `model_name`, `revision`, `enable_thinking`,
`template_path`, `template_sha256`, `tokenizer_path`, `tokenizer_sha256`,
`tokenizer_config_path`, and `tokenizer_config_sha256`. Paths resolve relative
to the parent of the config directory (the project root for `configs/`). Use
absolute paths for configs elsewhere. Boolean thinking values are strict.

`RLMOpsdEnv` accepts `prompt_config` as a config object or YAML path. Root
requests receive `extra_body.chat_template_kwargs.enable_thinking` from it;
contradictory per-request settings fail rather than diverging across variants.
Other sampling fields are preserved. Set the inference server's chat template
to the checked-in `prompts/chat_template.jinja` as well; the pinned prime-rl
`chat_template` inference key passes this to vLLM's `--chat-template`. A client
request cannot establish which template a remote server actually loaded.
Recursive roots inherit the same prompt configuration, manual version and
variant; their subsequent turns retain provider reasoning fields. Request-level
`chat_template` overrides are rejected. General-purpose leaf requests continue
to use their separate frozen client.

## Verification boundary

Unit tests use a small real BPE tokenizer, including deliberately unmerged token
IDs whose decode/re-encode result differs. The separate smoke check uses the real
Qwen vocabulary and the exact pinned template. Neither is model inference.
Server deployment must verify renderer/tokenizer equality. The training sample
builder preserves recorded rollout IDs and maps teacher causal positions; see
[OPSD_TRAIN.md](OPSD_TRAIN.md).
Existing M2 held-out coverage restrictions are unchanged.
