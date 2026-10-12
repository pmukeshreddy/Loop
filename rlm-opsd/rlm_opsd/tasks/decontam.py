from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

from .models import BENCHMARKS, SPLITS, normalized


@dataclass
class HeldoutRecord:
    benchmark: str
    task_id: str
    query: str
    source_refs: list[dict]


@dataclass
class HeldoutIndex:
    records: list[HeldoutRecord] = field(default_factory=list)
    # Complete means queries AND all source documents/entries for the reserved
    # snapshot. A downloaded question-only list never satisfies this contract.
    coverage: dict = field(default_factory=dict)

    def missing(self):
        counts = Counter(record.benchmark for record in self.records)
        return [name for name in BENCHMARKS if not (
            self.coverage.get(name, {}).get('complete', False)
            and self.coverage[name].get('record_count') == counts[name]
            and counts[name] > 0
            and self.coverage[name].get('revision')
            and all(record.source_refs for record in self.records if record.benchmark == name))]

    def write(self, path):
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')

    @classmethod
    def load(cls, path):
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        records = [HeldoutRecord(**row) for row in raw['records']]
        if any(record.benchmark not in BENCHMARKS or not record.query.strip() for record in records):
            raise ValueError('invalid heldout index record')
        identities = [(r.benchmark, r.task_id) for r in records]
        if len(set(identities)) != len(identities):
            raise ValueError('duplicate heldout index ID')
        return cls(records, raw.get('coverage', {}))


def grams(text, n):
    words = normalized(text).split()
    width = min(n, len(words))
    return {tuple(words[i:i + width]) for i in range(len(words) - width + 1)} if width else set()


def decontaminate(tasks, heldout, *, ngram_size, overlap_threshold):
    if not isinstance(ngram_size, int) or ngram_size < 1 or not 0 <= overlap_threshold < 1:
        raise ValueError('invalid n-gram size or overlap threshold')
    exact, postings, source_ids, content_hashes = defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(set)
    heldout_grams = []
    for i, record in enumerate(heldout.records):
        exact[normalized(record.query)].add(i)
        word_grams = grams(record.query, ngram_size)
        heldout_grams.append(word_grams)
        for gram in word_grams:
            postings[gram].add(i)
        for ref in record.source_refs:
            source_ids[(ref['dataset'], ref['item_id'])].add(i)
            content_hashes[ref['sha256']].add(i)
    counts = dict(exact_query=0, near_query=0, shared_source=0, shared_content=0)
    kept, dropped, by_split = [], [], defaultdict(lambda: dict(input=0, kept=0, dropped=0))
    for task in tasks:
        if task.split not in SPLITS:
            raise ValueError('only train/dev candidates may pass through decontamination')
        by_split[task.split]['input'] += 1
        hits = {}
        query = normalized(task.query)
        if query in exact:
            hits['exact_query'] = set(exact[query])
        else:
            query_grams = grams(task.query, ngram_size)
            possible = set().union(*(postings.get(gram, set()) for gram in query_grams)) if query_grams else set()
            for i in possible:
                reference = heldout_grams[i]
                similarity = len(query_grams & reference) / len(query_grams | reference)
                if similarity > overlap_threshold:
                    hits.setdefault('near_query', set()).add(i)
        for ref in task.source_refs:
            for rule, found in [('shared_source', source_ids.get((ref['dataset'], ref['item_id']))),
                                ('shared_content', content_hashes.get(ref['sha256']))]:
                if found:
                    hits.setdefault(rule, set()).update(found)
        if hits:
            by_split[task.split]['dropped'] += 1
            for rule in hits:
                counts[rule] += 1
            dropped.append(dict(task_id=task.task_id, split=task.split, reasons={
                rule: sorted(f'{heldout.records[i].benchmark}:{heldout.records[i].task_id}' for i in matches)
                for rule, matches in sorted(hits.items())}))
        else:
            by_split[task.split]['kept'] += 1
            kept.append(task)
    missing = heldout.missing()
    return kept, dict(input_total=len(kept) + len(dropped), kept_total=len(kept), dropped_total=len(dropped),
                      by_rule=counts, by_split=dict(by_split), dropped=dropped,
                      ngram_size=ngram_size, overlap_threshold=overlap_threshold,
                      similarity='word n-gram Jaccard > threshold; NFKC/casefold/word normalization',
                      heldout_records=len(heldout.records), coverage=heldout.coverage,
                      coverage_complete=not missing, missing_benchmarks=missing)


_QUERY_INDEX = {}


def query_overlap(query, heldout, *, ngram_size, overlap_threshold):
    """Fast screen used during generation; the release build reruns full decontamination."""
    key = (id(heldout), ngram_size)
    if key not in _QUERY_INDEX:
        exact, postings, held = {}, defaultdict(set), []
        for i, record in enumerate(heldout.records):
            exact.setdefault(normalized(record.query), i)
            word_grams = grams(record.query, ngram_size)
            held.append(word_grams)
            for gram in word_grams:
                postings[gram].add(i)
        _QUERY_INDEX[key] = (exact, postings, held)
    exact, postings, held = _QUERY_INDEX[key]
    text = normalized(query)
    if text in exact:
        record = heldout.records[exact[text]]
        return f'exact query match: {record.benchmark}:{record.task_id}'
    query_grams = grams(query, ngram_size)
    for i in set().union(*(postings.get(g, set()) for g in query_grams)) if query_grams else ():
        similarity = len(query_grams & held[i]) / len(query_grams | held[i])
        if similarity > overlap_threshold:
            record = heldout.records[i]
            return f'near query match {similarity:.2f}: {record.benchmark}:{record.task_id}'
    return None
