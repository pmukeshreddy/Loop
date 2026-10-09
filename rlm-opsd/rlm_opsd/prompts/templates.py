"""SPEC §3 text builders. No task answers or arbitrary info dictionaries enter here."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from rlm_opsd.harness.protocol import context_metadata


ROOT = Path(__file__).resolve().parents[2]
NAMES = ('context_type', 'context_total_length', 'chunk_info', 'context_prefix',
         'subcall_max_chars', 'subcall_chunk_chars', 'stdout_max_chars', 'max_turns')
PLACEHOLDERS = re.compile(r'\{(' + '|'.join(NAMES) + r')\}')


def checked_text(path, checksum):
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != checksum:
        raise ValueError(f'prompt source checksum mismatch: {path}')
    return payload.decode('utf-8')


def render_named(template, values):
    """Substitute only approved names, once; preserve all other literal braces."""
    missing = set(PLACEHOLDERS.findall(template)) - values.keys()
    if missing:
        raise ValueError('missing prompt placeholders: ' + ', '.join(sorted(missing)))
    return PLACEHOLDERS.sub(lambda match: str(values[match[1]]), template)


@dataclass(frozen=True)
class PromptPair:
    student_system: str
    manual: str
    query: str
    manual_version: str

    @property
    def teacher_system(self):
        return self.student_system + '\n\n' + self.manual

    def messages(self, variant):
        if variant not in ('student', 'teacher'):
            raise ValueError('prompt variant must be student or teacher')
        system = self.student_system if variant == 'student' else self.teacher_system
        return [dict(role='system', content=system), dict(role='user', content=self.query)]


@dataclass(frozen=True, init=False)
class PromptBuilder:
    student_template: str
    manual_template: str
    manual_version: str

    def __init__(self, source_dir=None, *, manual_version=None):
        source = Path(source_dir) if source_dir is not None else ROOT / 'prompts'
        registry = json.loads((source / 'versions.json').read_text())
        version = manual_version or registry['active_manual']
        if version not in registry['manuals'] or not re.fullmatch(r'manual_v[1-9][0-9]*', version):
            raise ValueError('unregistered manual version')
        record = registry['manuals'][version]
        student = checked_text(source / 'student_system.md', registry['student_sha256'])
        manual = checked_text(source / record['path'], record['sha256'])
        if version == registry['active_manual']:
            checked_text(source / 'teacher_manual.md', record['sha256'])
        # The privileged addition can depend on operating limits, never on task
        # metadata/query/answers. The shared API block carries permitted metadata.
        if set(PLACEHOLDERS.findall(manual)) & set(NAMES[:4]):
            raise ValueError('manual must be task-independent')
        object.__setattr__(self, 'student_template', student)
        object.__setattr__(self, 'manual_template', manual)
        object.__setattr__(self, 'manual_version', version)

    @classmethod
    def load(cls, source_dir=None, *, manual_version=None):
        return cls(source_dir, manual_version=manual_version)

    def build(self, *, query, context, config):
        if not isinstance(query, str):
            raise TypeError('query must be str')
        metadata = context_metadata(context, config.prefix_chars)
        lengths = metadata['context_lengths']
        chunk_info = f', split into {len(lengths)} chunks with lengths {lengths}' if isinstance(context, list) else ''
        values = dict(context_type=metadata['context_type'], context_total_length=metadata['context_total_length'],
                      context_prefix=metadata['context_prefix'], chunk_info=chunk_info,
                      subcall_max_chars=config.max_subcall_chars, subcall_chunk_chars=config.subcall_chunk_chars,
                      stdout_max_chars=config.stdout_max_chars, max_turns=config.max_turns)
        return PromptPair(render_named(self.student_template, values), render_named(self.manual_template, values),
                          query, self.manual_version)
