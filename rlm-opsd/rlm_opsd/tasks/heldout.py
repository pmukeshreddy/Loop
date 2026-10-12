"""Strict adapters for reserved evaluation snapshots; never substitute datasets."""
from dataclasses import dataclass, field
import json
import re
from pathlib import Path

from .models import BENCHMARKS, canonical, digest, source_ref


@dataclass
class HeldoutTask:
    """A reserved evaluation item. Only its query and source refs enter the decontamination index."""
    task_id: str
    family: str
    split: str
    context: str | list[str]
    query: str
    answer: object
    answer_type: str
    knobs: dict
    source: str
    source_refs: list[dict]
    tags: list[str] = field(default_factory=list)
    domain: str = 'long_context'


def adapt_heldout(benchmark, raw, *, revision, license, context_record=None, context_len=None, documents=None):
    if benchmark not in BENCHMARKS or benchmark == 'deepswe' or not revision or not license:
        raise ValueError('known benchmark, revision and source license required')
    refs = None
    answer_type = 'exact'
    if benchmark == 'sniah':
        if len(raw['outputs']) != 1:
            raise ValueError('S-NIAH requires a single needle answer')
        context = raw['input']
        queries = re.findall(r'What (?:is|are)[^?]+\?', context)
        query = raw.get('question') or (queries[-1] if queries else '')
        if not query:
            raise ValueError('S-NIAH export needs a recoverable question')
        answer = raw['outputs'][0]
    elif benchmark in ('oolong', 'oolong_pairs'):
        record = raw if benchmark == 'oolong' else context_record
        if not record or 'context_window_text' not in record:
            raise ValueError('matching unlabelled OOLONG context required')
        if record.get('dataset') != 'trec_coarse':
            raise ValueError('OOLONG requires the trec_coarse subset; no alternative subset allowed')
        if benchmark == 'oolong_pairs' and (context_len is None or record.get('context_len') != context_len):
            raise ValueError('OOLONG-Pairs context length mismatch')
        context, query, answer = record['context_window_text'], raw['question'], raw['answer']
        if benchmark == 'oolong_pairs':
            if not isinstance(answer, list):
                raise ValueError('pairs answers must be a list')
            answer_type = 'list_f1'
        elif raw['answer_type'] == 'numeric':
            answer = int(answer)
            answer_type = 'numeric'
        elif raw['answer_type'] in ('list_of_answers', 'list_f1'):
            answer = json.loads(answer) if isinstance(answer, str) else answer
            answer_type = 'list_f1'
        entries = re.findall(r'Instance:\s*(.*)', context)
        refs = [source_ref('TREC', revision, digest(text), text) for text in sorted(set(entries))]
        if not refs:
            refs = [source_ref('oolong/trec_coarse', revision, record.get('context_window_id', digest(context)), context)]
    elif benchmark == 'longbench_v2_codeqa':
        if raw['domain'] != 'Code Repository Understanding' or raw['sub_domain'] != 'Code repo QA':
            raise ValueError('LongBench import is restricted to Code Repository Understanding / Code repo QA')
        context, answer = raw['context'], raw['answer']
        if answer not in 'ABCD' or len(answer) != 1:
            raise ValueError('invalid multiple-choice answer')
        query = raw['question'] + '\n' + '\n'.join(f'{letter}. {raw["choice_" + letter]}' for letter in 'ABCD')
        answer_type = 'multiple_choice'
    else:
        if documents is None or len(documents) != 1000 or len({doc['docid'] for doc in documents}) != 1000:
            raise ValueError('BrowseComp-Plus requires exactly 1000 distinct selected documents')
        if not {doc['docid'] for doc in raw.get('gold_docs', [])} <= {doc['docid'] for doc in documents}:
            raise ValueError('BrowseComp selection omits gold documents')
        context = [f"Document {doc['docid']}\n{doc['text']}" for doc in documents]
        query, answer = raw['query'], raw['answer']
        refs = [source_ref('Tevatron/browsecomp-plus-corpus', revision, doc['docid'], doc['text']) for doc in documents]
    task_id = benchmark + '-' + digest(canonical(dict(query=query, context=context)))[:20]
    if refs is None:
        refs = [source_ref(benchmark, revision, digest(canonical(context)), canonical(context))]
    return HeldoutTask(task_id=task_id, family=benchmark, split='eval_heldout', context=context,
                query=query, answer=answer, answer_type=answer_type, knobs=dict(revision=revision),
                source=f'{benchmark}@{revision}; {license}', source_refs=refs,
                tags=['eval_heldout'], domain='code' if benchmark == 'longbench_v2_codeqa' else 'long_context')


def load_heldout_snapshot(path, *, benchmark, revision, license):
    """Load JSON arrays or JSONL exports. BrowseComp input must be decrypted.

    OOLONG-Pairs rows include context_record/context_len; BrowseComp rows include
    the selected documents list. These inputs are required, never synthesized.
    """
    with Path(path).open(encoding='utf-8') as stream:
        first = ''
        while not first:
            char = stream.read(1)
            if not char:
                raise ValueError('empty heldout snapshot')
            if not char.isspace():
                first = char
        stream.seek(0)
        rows = json.load(stream) if first == '[' else (json.loads(line) for line in stream if line.strip())
        seen = set()
        for raw in rows:
            if benchmark == 'oolong' and raw.get('dataset') != 'trec_coarse':
                continue
            if benchmark == 'longbench_v2_codeqa' and (raw.get('domain'), raw.get('sub_domain')) != (
                    'Code Repository Understanding', 'Code repo QA'):
                continue
            task = adapt_heldout(benchmark, raw, revision=revision, license=license,
                                 context_record=raw.get('context_record'), context_len=raw.get('context_len'),
                                 documents=raw.get('documents'))
            if task.task_id in seen:
                raise ValueError('duplicate heldout task')
            seen.add(task.task_id)
            yield task
