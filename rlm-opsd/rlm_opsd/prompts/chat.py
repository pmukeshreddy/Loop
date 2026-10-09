"""One pinned chat template and thinking setting for both initial prefixes."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import urllib.request

from pydantic import Field, StrictBool
import yaml

from rlm_opsd.harness.config import StrictConfig
from .templates import ROOT, checked_text


class PromptConfig(StrictConfig):
    model_name: str = Field(min_length=1)
    revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    template_path: Path
    template_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    tokenizer_path: Path
    tokenizer_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    tokenizer_config_path: Path
    tokenizer_config_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    enable_thinking: StrictBool

    @classmethod
    def from_yaml(cls, path=None):
        path = Path(path) if path is not None else ROOT / 'configs/prompts.yaml'
        values = yaml.safe_load(path.read_text())
        for name in ('template_path', 'tokenizer_path', 'tokenizer_config_path'):
            values[name] = (path.resolve().parent.parent / values[name]).resolve()
        return cls.model_validate(values)

    def sampling_args(self, supplied):
        args = dict(supplied)
        extra = dict(args.get('extra_body') or {})
        if 'chat_template' in extra:
            raise ValueError('request cannot override the pinned chat template')
        template_kwargs = dict(extra.get('chat_template_kwargs') or {})
        if 'enable_thinking' in template_kwargs and template_kwargs['enable_thinking'] is not self.enable_thinking:
            raise ValueError('request thinking setting differs from pinned prompt config')
        template_kwargs['enable_thinking'] = self.enable_thinking
        extra['chat_template_kwargs'] = template_kwargs
        args['extra_body'] = extra
        return args


def prepare_tokenizer(config):
    """Fetch only missing tokenizer artifacts; a changed cache fails closed."""
    checked_text(config.template_path, config.template_sha256)
    for name, path, checksum in (
        ('tokenizer.json', config.tokenizer_path, config.tokenizer_sha256),
        ('tokenizer_config.json', config.tokenizer_config_path, config.tokenizer_config_sha256),
    ):
        if not path.exists():
            url = f'https://huggingface.co/{config.model_name}/resolve/{config.revision}/{name}'
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = response.read()
            if hashlib.sha256(payload).hexdigest() != checksum:
                raise ValueError(f'tokenizer download checksum mismatch: {name}')
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_bytes(payload)
            temporary.replace(path)
        checked_text(path, checksum)


def load_tokenizer(config):
    from transformers import PreTrainedTokenizerFast

    checked_text(config.tokenizer_path, config.tokenizer_sha256)
    options = json.loads(checked_text(config.tokenizer_config_path, config.tokenizer_config_sha256))
    # The serialized backend contains the vocabulary, normalizer, merges and
    # added-token definitions. No AutoModel, remote code or weight loading.
    return PreTrainedTokenizerFast(tokenizer_file=str(config.tokenizer_path),
        **{key: options.get(key) for key in ('bos_token', 'eos_token', 'pad_token', 'unk_token')},
        clean_up_tokenization_spaces=False)


@dataclass(frozen=True)
class PrefixPair:
    student_ids: tuple[int, ...]
    teacher_ids: tuple[int, ...]
    student_text: str
    teacher_text: str
    template_sha256: str
    enable_thinking: bool
    manual_version: str


class ChatRenderer:
    def __init__(self, config, *, tokenizer=None):
        self.config = config
        self.template = checked_text(config.template_path, config.template_sha256)
        self.tokenizer = load_tokenizer(config) if tokenizer is None else tokenizer

    def prefixes(self, pair):
        texts, tokens = [], []
        for variant in ('student', 'teacher'):
            arguments = dict(chat_template=self.template, enable_thinking=self.config.enable_thinking,
                             add_generation_prompt=True, truncation=False, padding=False)
            messages = pair.messages(variant)
            texts.append(self.tokenizer.apply_chat_template(messages, tokenize=False, **arguments))
            tokens.append(tuple(self.tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False, **arguments)))
        return PrefixPair(tokens[0], tokens[1], texts[0], texts[1], self.config.template_sha256,
                          self.config.enable_thinking, pair.manual_version)
