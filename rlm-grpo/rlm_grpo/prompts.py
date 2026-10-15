"""Phase-owned policy assets with the checkpoint's established RLM protocol."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

ASSETS = Path(__file__).with_name("assets")
POLICY_SHA256 = "1aa4f640928ecac721c42e2b33244abf7c5f681474c8208c71704747b67cbb1b"
NAMES = ("context_type", "context_total_length", "chunk_info", "context_prefix",
         "subcall_max_chars", "subcall_chunk_chars", "stdout_max_chars", "max_turns")
PLACEHOLDERS = re.compile(r"\{(" + "|".join(NAMES) + r")\}")


def checked_text(path, checksum):
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != checksum:
        raise ValueError(f"Prompt source checksum mismatch: {path}")
    return payload.decode("utf-8")


def render_named(template, values):
    """Replace known placeholders once, preserving literal Python braces."""
    missing = set(PLACEHOLDERS.findall(template)) - values.keys()
    if missing:
        raise ValueError("Missing prompt placeholders: " + ", ".join(sorted(missing)))
    return PLACEHOLDERS.sub(lambda match: str(values[match[1]]), template)


@dataclass(frozen=True)
class PromptConfig:
    template_path: Path = ASSETS / "chat_template.jinja"
    template_sha256: str = "a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715"
    enable_thinking: bool = True

    def system_prompt(self):
        return checked_text(ASSETS / "policy_system.md", POLICY_SHA256)

    def sampling_args(self, supplied):
        args = dict(supplied)
        extra = dict(args.get("extra_body") or {})
        if "chat_template" in extra:
            raise ValueError("Request cannot override the pinned chat template")
        template_kwargs = dict(extra.get("chat_template_kwargs") or {})
        if ("enable_thinking" in template_kwargs
                and template_kwargs["enable_thinking"] is not self.enable_thinking):
            raise ValueError("Request thinking setting differs from the GRPO policy assets")
        template_kwargs["enable_thinking"] = self.enable_thinking
        extra["chat_template_kwargs"] = template_kwargs
        args["extra_body"] = extra
        return args
