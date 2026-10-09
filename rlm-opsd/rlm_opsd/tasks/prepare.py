import hashlib
import json
from pathlib import Path
import urllib.request

from .decontam import HeldoutIndex, HeldoutRecord
from .sources import ClassificationCorpus


def checked_source(source, *, download=False):
    path = Path(source['path'])
    if not path.exists():
        if not download:
            raise ValueError(f'missing source {path}; run tasks prepare')
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(source['url'], timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            raise ValueError(f'download checksum mismatch: {path}')
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError(f'source checksum mismatch: {path}')
    return path


def load_corpora(config):
    result = {}
    for split in ('train', 'dev_behavior'):
        source = config['classification_sources'][split]
        checked_source(source)
        result[split] = ClassificationCorpus.from_banking_csv(**{
            key: source[key] for key in ('path', 'sha256', 'revision', 'partition', 'ambiguity_policy')})
    return result


def prepare_sources(config):
    for source in config['classification_sources'].values():
        checked_source(source, download=True)
    records, coverage = [], {}
    for source in config.get('heldout_question_sources', []):
        path = checked_source(source, download=True)
        rows = json.loads(path.read_text(encoding='utf-8'))
        for row in rows:
            records.append(HeldoutRecord(benchmark=source['benchmark'], task_id=str(row['id']),
                                         query=row['question'], source_refs=[]))
        coverage[source['benchmark']] = dict(complete=False, revision=source['revision'], record_count=len(rows),
            source_sha256=source['sha256'], license=source['license'], reason='queries only; context/source coverage missing')
    for source in config.get('heldout_snapshots', []):
        from .heldout import load_heldout_snapshot
        path = checked_source(source)
        imported = [HeldoutRecord(source['benchmark'], task.task_id, task.query, task.source_refs)
                    for task in load_heldout_snapshot(path, benchmark=source['benchmark'],
                                                      revision=source['revision'], license=source['license'])]
        if not imported:
            raise ValueError(f'no matching heldout tasks in {path}')
        records = [record for record in records if record.benchmark != source['benchmark']]
        records.extend(imported)
        coverage[source['benchmark']] = dict(complete=source.get('complete', False), revision=source['revision'],
            record_count=len(imported), source_sha256=source['sha256'], license=source['license'],
            reason='complete reserved snapshot' if source.get('complete') else 'partial snapshot')
    index = HeldoutIndex(records=records, coverage=coverage)
    path = Path(config['heldout_index']); path.parent.mkdir(parents=True, exist_ok=True)
    index.write(path)
    return dict(heldout_records=len(records), coverage_complete=not index.missing(), missing_benchmarks=index.missing(),
                classification_sources={key: value.import_report for key, value in load_corpora(config).items()})
