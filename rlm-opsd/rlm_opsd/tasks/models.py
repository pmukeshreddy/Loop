"""Task taxonomy, generated-candidate schema and the released manifest record."""
from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from typing import Any, Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Primary organization: the RLM behavior a task gives practice in. DeepSWE
# repository work (tracing, debugging, implementation) is the setting.
BEHAVIORS = ('inspect_locate', 'chunked_subcalls', 'recursive_decomposition',
             'persistent_state', 'combine_verify_finish', 'direct_solve')
FAMILIES = BEHAVIORS  # a released task's family is its primary intended behavior
BEHAVIOR_DESCRIPTIONS = {
    'inspect_locate': 'Inspect context and locate relevant evidence using code.',
    'chunked_subcalls': 'Select and chunk relevant context for bounded semantic sub-calls.',
    'recursive_decomposition': 'Decompose investigations into useful recursive calls.',
    'persistent_state': 'Maintain and reuse intermediate results in persistent REPL variables.',
    'combine_verify_finish': 'Combine and check findings programmatically, then finish correctly with FINAL or FINAL_VAR.',
    'direct_solve': 'Recognize when a task can be solved directly without delegation.',
}
# Starting settings; the source analyst may add repository-supported settings.
SETTINGS = ('dependency_tracing', 'scattered_evidence_debugging', 'change_impact',
            'multi_module_fix', 'test_failure_investigation', 'implementation')
ANSWER_KINDS = ('patch', 'test_ids', 'symbols', 'value')
ANSWER_FORMATS = ('unified_diff', 'set', 'ordered_list', 'scalar', 'object')
SPLITS = ('train', 'dev_behavior')
BENCHMARKS = ('sniah', 'browsecomp_plus', 'oolong', 'oolong_pairs', 'longbench_v2_codeqa', 'deepswe')
DOMAIN = 'deepswe'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalized(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


def source_ref(dataset, revision, item_id, text):
    return dict(dataset=dataset, revision=revision, item_id=str(item_id), sha256=digest(normalized(text)))


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ContextScope(StrictModel):
    scope: Literal['repository', 'files']
    files: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_files(self):
        if self.scope == 'files' and not self.files:
            raise ValueError('files scope needs at least one file')
        if any(p.startswith('/') or '..' in p.split('/') for p in self.files):
            raise ValueError('context files must be repository-relative')
        return self


class Evidence(StrictModel):
    path: str
    symbol: str | None = None
    why: str


class CandidateSpec(StrictModel):
    """One generated task before materialization; validated, never shown to the student."""
    setting: str = Field(pattern=r'^[a-z][a-z0-9_]{2,48}$')
    primary_behavior: Literal[BEHAVIORS]
    rlm_behaviors: list[Literal[BEHAVIORS]] = Field(min_length=1)
    behavior_rationale: dict[str, str]
    question: str = Field(min_length=40)
    answer_kind: Literal[ANSWER_KINDS]
    answer_format: Literal[ANSWER_FORMATS]
    context: ContextScope
    include_failure_log: bool = False
    setup_patch: str | None = None        # creates the starting state the solver sees
    probe_patch: str | None = None        # hypothetical change for impact questions; never applied to context
    hidden_tests_patch: str | None = None  # implementation acceptance tests; applied only at verification
    evidence: list[Evidence] = Field(min_length=1)
    expected_answer: Any = None           # the generator's belief; never used as the oracle
    notes: str = ''

    @model_validator(mode='after')
    def check_consistency(self):
        if self.primary_behavior not in self.rlm_behaviors:
            raise ValueError('rlm_behaviors must include primary_behavior')
        if len(set(self.rlm_behaviors)) != len(self.rlm_behaviors):
            raise ValueError('duplicate rlm_behaviors')
        if set(self.behavior_rationale) != set(self.rlm_behaviors) or not all(
                len(v.strip()) >= 30 for v in self.behavior_rationale.values()):
            raise ValueError('each intended behavior needs a substantive rationale')
        if 'direct_solve' in self.rlm_behaviors and len(self.rlm_behaviors) > 1 and {
                'chunked_subcalls', 'recursive_decomposition'} & set(self.rlm_behaviors):
            raise ValueError('direct_solve contradicts delegation behaviors')
        if self.primary_behavior == 'direct_solve' and self.context.scope != 'files':
            raise ValueError('direct_solve tasks use a focused files context')
        kind, fmt = self.answer_kind, self.answer_format
        if kind == 'patch':
            if fmt != 'unified_diff' or not (self.setup_patch or self.hidden_tests_patch):
                raise ValueError('patch tasks need unified_diff answers and a setup or hidden-test patch')
            if self.probe_patch:
                raise ValueError('patch tasks do not use probe_patch')
        elif fmt == 'unified_diff':
            raise ValueError('only patch tasks answer with a diff')
        if kind == 'test_ids' and (not self.probe_patch or fmt != 'set'):
            raise ValueError('test_ids tasks need a probe_patch and set answers')
        if kind != 'test_ids' and self.probe_patch:
            raise ValueError('probe_patch is only for test_ids tasks')
        if kind == 'symbols' and fmt not in ('set', 'ordered_list'):
            raise ValueError('symbols answers are lists')
        if self.include_failure_log and not self.setup_patch:
            raise ValueError('a failure log requires a setup_patch that breaks behavior')
        if self.hidden_tests_patch and kind != 'patch':
            raise ValueError('hidden tests only verify patch tasks')
        return self


@dataclass
class Task:
    """A released task. `answer` and references stay out of every model prompt."""
    task_id: str
    split: str
    family: str
    rlm_behaviors: list[str]
    behavior_rationale: dict
    setting: str
    query: str
    context: list[str]
    answer: Any
    answer_type: str
    answer_format: str
    size_bucket: int
    repo: dict
    source: str
    source_refs: list[dict]
    tags: list[str] = field(default_factory=list)
    domain: str = DOMAIN
    parent_id: str | None = None
    variation: dict | None = None
    practice: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    reference_path: str = ''
    provenance: dict = field(default_factory=dict)

    def manifest(self, context_path):
        row = asdict(self)
        context = row.pop('context')
        row.update(context_path=context_path, context_format='list',
                   context_chars=sum(map(len, context)), context_sha256=digest(canonical(context)))
        return row

    @classmethod
    def from_manifest(cls, row, context):
        row = {k: v for k, v in row.items() if k in cls.__dataclass_fields__}
        return cls(context=context, **row)


def size_bucket(chars, buckets):
    for bucket in sorted(buckets):
        if chars <= bucket:
            return bucket
    raise ValueError(f'context of {chars} chars exceeds the largest size bucket')
