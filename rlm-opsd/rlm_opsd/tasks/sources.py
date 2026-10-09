import csv
from dataclasses import dataclass, field
from pathlib import Path

from .models import canonical, digest, normalized, source_ref


@dataclass
class ClassificationCorpus:
    records: list[dict]
    name: str
    revision: str
    license: str
    labels_by_text: dict
    refs_by_text: dict
    import_report: dict = field(default_factory=dict)

    @classmethod
    def from_records(cls, records, *, name, revision, license):
        if 'trec' in name.casefold():
            raise ValueError('TREC sources are reserved for heldout evaluation')
        if not revision or not license or not name or not records:
            raise ValueError('source, revision, license and records are required')
        labels, refs, unique, ids = {}, {}, [], set()
        for row in sorted(records, key=lambda r: str(r['id'])):
            if row['id'] in ids:
                raise ValueError('duplicate source record ID')
            ids.add(row['id'])
            key = normalized(row['text'])
            if not key or not row['label']:
                raise ValueError('empty source text or label')
            if key in labels and labels[key] != row['label']:
                raise ValueError('conflicting labels for normalized source text')
            if key not in labels:
                labels[key] = row['label']
                refs[key] = source_ref(name, revision, row['id'], row['text'])
                unique.append(dict(row))
        return cls(unique, name, revision, license, labels, refs)

    @classmethod
    def from_banking_csv(cls, path, *, sha256, revision, partition, ambiguity_policy='reject'):
        path = Path(path)
        import hashlib
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise ValueError(f'source checksum mismatch: {path}')
        with path.open(encoding='utf-8', newline='') as stream:
            records = [dict(id=f'{partition}:{i}', text=row['text'], label=row['category'])
                       for i, row in enumerate(csv.DictReader(stream))]
        raw_count = len(records)
        if ambiguity_policy not in ('reject', 'drop'):
            raise ValueError('invalid ambiguity policy')
        if ambiguity_policy == 'drop':
            from collections import defaultdict
            labels = defaultdict(set)
            for row in records:
                labels[normalized(row['text'])].add(row['label'])
            records = [row for row in records if len(labels[normalized(row['text'])]) == 1]
        result = cls.from_records(records, name='PolyAI/banking77', revision=revision, license='CC-BY-4.0')
        result.import_report = dict(raw_rows=raw_count, ambiguous_rows_dropped=raw_count - len(records),
                                    duplicate_rows_dropped=len(records) - len(result.records),
                                    retained_rows=len(result.records), sha256=sha256, partition=partition,
                                    revision=revision, license='CC-BY-4.0')
        return result

    @property
    def fingerprint(self):
        return digest(canonical(dict(records=self.records, name=self.name, revision=self.revision, license=self.license)))

    def label_for(self, text):
        try:
            return self.labels_by_text[normalized(text)]
        except KeyError as exc:
            raise ValueError('unknown classification source text') from exc

    def refs_for(self, texts):
        return [self.refs_by_text[key] for key in sorted({normalized(text) for text in texts})]
