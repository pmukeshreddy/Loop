from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
import unicodedata


FAMILIES = ('sparse_retrieval', 'multi_hop', 'linear_aggregation', 'quadratic_pairs',
            'repo_qa', 'small_context_control')
BENCHMARKS = ('sniah', 'browsecomp_plus', 'oolong', 'oolong_pairs', 'longbench_v2_codeqa')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalized(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


def source_ref(dataset, revision, item_id, text):
    return dict(dataset=dataset, revision=revision, item_id=str(item_id), sha256=digest(normalized(text)))


@dataclass(frozen=True)
class TaskSpec:
    family: str
    knobs: dict
    seed: int
    split: str = 'train'


@dataclass
class Task:
    task_id: str
    family: str
    split: str
    context: str | list[str]
    query: str
    answer: str | int | list[str]
    answer_type: str
    knobs: dict
    seed: int
    source: str
    source_refs: list[dict]
    tags: list[str] = field(default_factory=list)
    domain: str = 'long_context'

    def manifest(self, context_path):
        row = asdict(self)
        context = row.pop('context')
        row.update(context_path=context_path,
                   context_format='str' if isinstance(context, str) else 'list',
                   context_chars=len(context) if isinstance(context, str) else sum(map(len, context)),
                   context_sha256=digest(canonical(context)))
        return row

    @classmethod
    def from_manifest(cls, row, context):
        row = {k: v for k, v in row.items() if k in cls.__dataclass_fields__}
        return cls(context=context, **row)
