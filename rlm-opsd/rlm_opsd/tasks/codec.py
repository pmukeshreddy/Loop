"""Lossless, human-readable task encodings; list chunks end at record boundaries."""
import csv
import io
import json


ENCODINGS = ('plain', 'jsonl', 'csv', 'logs', 'markdown')


def render_records(records, *, encoding, structure, chunk_chars=4096):
    if encoding not in ENCODINGS or structure not in ('str', 'list') or chunk_chars <= 0:
        raise ValueError('invalid encoding, structure or chunk size')
    chunks, pieces, count = [], [], 0
    for index, record in enumerate(records):
        if encoding == 'jsonl':
            text = json.dumps(record, ensure_ascii=False) + '\n'
        elif encoding == 'csv':
            stream = io.StringIO(newline='')
            writer = csv.writer(stream, lineterminator='\n')
            # A two-column record encoding avoids schema loss for mixed records.
            writer.writerow(['record', json.dumps(record, ensure_ascii=False)])
            text = stream.getvalue()
        else:
            fields = '\t'.join(k + '=' + json.dumps(v, ensure_ascii=False) for k, v in record.items())
            prefix = {'plain': '', 'logs': '[RECORD] ', 'markdown': '- Record: '}[encoding]
            text = prefix + fields + '\n'
        if structure == 'list' and pieces and count + len(text) > chunk_chars:
            chunks.append(''.join(pieces)); pieces, count = [], 0
        pieces.append(text); count += len(text)
    if pieces:
        chunks.append(''.join(pieces))
    return ''.join(chunks) if structure == 'str' else chunks


def parse_records(context, encoding):
    if encoding not in ENCODINGS:
        raise ValueError('unknown record encoding')
    chunks = [context] if isinstance(context, str) else context
    result = []
    for chunk in chunks:
        if encoding == 'csv':
            for kind, payload in csv.reader(io.StringIO(chunk, newline='')):
                if kind != 'record':
                    raise ValueError('invalid CSV record')
                result.append(json.loads(payload))
            continue
        for line in chunk.splitlines():
            if not line:
                continue
            if encoding == 'jsonl':
                result.append(json.loads(line))
            else:
                prefix = {'plain': '', 'logs': '[RECORD] ', 'markdown': '- Record: '}[encoding]
                if not line.startswith(prefix):
                    raise ValueError('invalid record prefix')
                fields = [field.split('=', 1) for field in line[len(prefix):].split('\t')]
                result.append({key: json.loads(value) for key, value in fields})
    return result
