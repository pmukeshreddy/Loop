import copy
from collections import Counter
from datetime import date, timedelta
from itertools import combinations
import random

from .codec import render_records
from .models import FAMILIES, Task, canonical, digest, source_ref


TAGS = {
    'sparse_retrieval': ['sparse', 'code_search', 'windowed_read', 'verify_hit'],
    'multi_hop': ['sparse', 'code_search', 'chained_search', 'verify_hit'],
    'linear_aggregation': ['dense', 'needs_subcalls', 'subcalls_in_loop', 'buffer_store', 'aggregate_in_code'],
    'quadratic_pairs': ['dense', 'needs_subcalls', 'aggregate_in_code', 'output_in_variable'],
    'repo_qa': ['code_search', 'windowed_read', 'subcall_on_matches'],
    'small_context_control': ['small_context'],
}


QUERY_WORDINGS = {
    'sparse_retrieval': (
        'Find the current values associated with these exact parcel IDs: {keys}.',
        'Look up each parcel ID in {keys} and report its current value. Match IDs exactly.',
        'Retrieve the current value for every parcel in {keys}, using exact ID matches.',
        'For the parcel IDs {keys}, extract their current values; ignore IDs that only partially match.',
    ),
    'multi_hop': (
        'Starting at {start}, follow exactly {hops} target links. What is the terminal value?',
        'Traverse {hops} target links from {start} and return the terminal value at the final node.',
        'What terminal value do you reach after exactly {hops} target-link steps beginning at {start}?',
        'Begin with node {start}. Take exactly {hops} target links, then report that node’s terminal value.',
    ),
    'count': (
        'How many entries{date_clause} express the intent {label}?',
        'Count the entries{date_clause} whose intent is {label}.',
        'Give the number of entries{date_clause} classified as {label}.',
        'Among entries{date_clause}, what is the total count for intent {label}?',
    ),
    'most_frequent': (
        'Which intent is most frequent among entries{date_clause}?',
        'Find the intent expressed by the largest number of entries{date_clause}.',
        'Among entries{date_clause}, report the intent with the highest count.',
        'Classify the entries{date_clause} and name their most common intent.',
    ),
    'pairs': (
        'Using entries{date_clause}, list all distinct user pairs where {condition}: {labels}.',
        'Find every distinct pair of users for which {condition}: {labels}. Use entries{date_clause}.',
        'Consider entries{date_clause}. Which distinct user pairs satisfy this condition: {condition}: {labels}?',
        'From entries{date_clause}, enumerate the distinct pairs of users such that {condition}: {labels}.',
    ),
    'small_context_control': (
        'What is the sum of the quantities for {group}?',
        'Add all quantities belonging to {group} and return the total.',
        'Report the total of the quantity values in {group}.',
        'For group {group}, calculate the sum of its quantities.',
    ),
    'definition': (
        'Which file defines function {symbol}?',
        'Find the file containing the definition of function {symbol}.',
        'Return the path of the file where function {symbol} is defined.',
        'Locate the definition of function {symbol} and report its file path.',
    ),
    'callers': (
        'List file:function for every function that calls {symbol}.',
        'Which functions call {symbol}? Return a list of file:function entries.',
        'Find all functions invoking {symbol} and list each as file:function.',
        'Return every caller of {symbol} as a list of file:function entries.',
    ),
    'config': (
        'What is the value assigned to {symbol}?',
        'Look up the assignment to {symbol} and return its value.',
        'Find the configured value of {symbol}.',
        'Report the value stored in configuration constant {symbol}.',
    ),
}


def generate(spec, corpus=None):
    if spec.split not in ('train', 'dev_behavior'):
        raise ValueError('heldout tasks must be imported, never generated as training tasks')
    if spec.family not in FAMILIES:
        raise ValueError('unknown family')
    rng = random.Random(spec.seed)
    k = dict(target_chars=8192, structure='str', encoding='jsonl', chunk_chars=4096,
             needles=2, hops=3, users=24, direct_read_max_chars=16384, **{})
    k.update(copy.deepcopy(spec.knobs))
    if not isinstance(spec.seed, int) or k['target_chars'] <= 0 or k['users'] < 2:
        raise ValueError('invalid seed, size or user count')
    if not 1 <= k['needles'] <= 8 or not 2 <= k['hops'] <= 4:
        raise ValueError('needles must be 1–8 and hops 2–4')
    if spec.family == 'small_context_control' and k['target_chars'] >= k['direct_read_max_chars']:
        raise ValueError('small context must be below the direct-read limit')
    if spec.family == 'repo_qa' and k['structure'] != 'list':
        raise ValueError('repo QA requires list-of-files context')
    # Rewording a query must not consume the context-generation RNG stream.
    query_rng = random.Random(f'{spec.seed}:query-wording')
    def phrase(kind, **params):
        k['query_variant'] = query_rng.randrange(len(QUERY_WORDINGS[kind]))
        return QUERY_WORDINGS[kind][k['query_variant']].format(**params)

    uid = f'{rng.getrandbits(64):016x}'
    records, answer, refs = [], None, []
    source = 'rlm-opsd synthetic-v1; CC0-1.0'
    family = spec.family
    if family == 'sparse_retrieval':
        keys = [f'parcel-{uid}-{i}' for i in range(k['needles'])]
        values = [f'{rng.getrandbits(48):012x}' for _ in keys]
        records = [dict(kind='fact', key=key, value=value) for key, value in zip(keys, values)]
        records += [dict(kind='fact', key=key + '-old', value=f'{rng.getrandbits(48):012x}') for key in keys]
        k['query_params'] = dict(keys=keys)
        query = phrase(family, keys=canonical(keys))
        query += ' Return the value for one ID, or a list of values in ID order for multiple IDs.'
        answer = values[0] if len(values) == 1 else values
    elif family == 'multi_hop':
        nodes = [f'node-{uid}-{i}' for i in range(k['hops'] + 1)]
        records = [dict(kind='link', key=a, target=b) for a, b in zip(nodes, nodes[1:])]
        answer = rng.choice(['Oslo', 'Lima', 'Kyoto', 'Accra', 'Riga'])
        records.append(dict(kind='terminal', key=nodes[-1], value=answer))
        records.append(dict(kind='terminal', key=nodes[0], value='decoy'))
        k['query_params'] = dict(start=nodes[0], hops=k['hops'])
        query = phrase(family, start=nodes[0], hops=k['hops'])
    elif family in ('linear_aggregation', 'quadratic_pairs'):
        if corpus is None:
            raise ValueError('classification corpus required')
        all_labels = sorted(set(corpus.labels_by_text.values()))
        if 'label_count' in k:
            count = k['label_count']
            if k.get('labels') or type(count) is not int or not 1 <= count <= len(all_labels):
                raise ValueError('label_count must fit the corpus and cannot be combined with explicit labels')
            labels = sorted(random.Random(f'{spec.seed}:labels').sample(all_labels, count))
        else:
            labels = k.get('labels') or all_labels
        if not set(labels) <= set(corpus.labels_by_text.values()):
            raise ValueError('unknown label in requested label set')
        available = [row for row in corpus.records if row['label'] in labels]
        if not available:
            raise ValueError('empty classification selection')
        requested = k.get('entries')
        if requested is not None and requested <= 0:
            raise ValueError('entries must be positive')
        count = requested or max(2, k['target_chars'] // 100)
        annotations = []
        def add_entries(number):
            for _ in range(number):
                row = rng.choice(available)
                record = dict(kind='entry', user=rng.randrange(1, k['users'] + 1),
                              date=str(date(2023, 1, 1) + timedelta(days=rng.randrange(180))), text=row['text'])
                records.append(record); annotations.append(row['label'])
        add_entries(count)
        if requested is None:
            while True:
                encoded = render_records(records, encoding=k['encoding'], structure='str')
                if len(encoded) >= k['target_chars']:
                    break
                add_entries(max(1, (k['target_chars'] - len(encoded)) // 100))
        k['entries'] = len(records)
        k['labels'] = labels
        k['source_fingerprint'] = corpus.fingerprint
        refs = corpus.refs_for(r['text'] for r in records)
        source = f'{corpus.name}@{corpus.revision}; {corpus.license}; generated user IDs/dates'
        after = str(date.fromisoformat(k.get('cutoff_date', '2023-03-31'))) if k.get('temporal_filter', True) else None
        filtered = [(r, label) for r, label in zip(records, annotations) if after is None or r['date'] > after]
        date_clause = f' dated strictly after {after}' if after else ''
        if family == 'linear_aggregation':
            operation = k.get('query_type', rng.choice(['count', 'most_frequent']))
            label = rng.choice(labels)
            k['query_params'] = dict(operation=operation, label=label, after=after)
            if operation == 'count':
                answer = sum(category == label for _, category in filtered)
                query = phrase(operation, date_clause=date_clause, label=label)
            elif operation == 'most_frequent':
                counts = Counter(category for _, category in filtered)
                answer = sorted(counts, key=lambda category: (-counts[category], category))[0] if counts else 'NONE'
                query = phrase(operation, date_clause=date_clause)
                query += ' Break ties lexicographically; return NONE if empty.'
            else:
                raise ValueError('invalid aggregation query type')
            query += ' Allowed intents: ' + ', '.join(labels) + '.'
        else:
            selected = rng.sample(labels, min(2, len(labels)))
            relation = k.get('pair_relation', 'both_have_any')
            k['query_params'] = dict(labels=selected, relation=relation, after=after)
            users = sorted({r['user'] for r, _ in filtered})
            labels_by_user = {user: {label for r, label in filtered if r['user'] == user} for user in users}
            if relation == 'both_have_any':
                eligible = [user for user in users if labels_by_user[user].intersection(selected)]
                pairs = combinations(eligible, 2)
                condition = 'both users have at least one entry with any of these intents'
            elif relation == 'cover_labels':
                pairs = ((a, b) for a, b in combinations(users, 2) if set(selected) <= labels_by_user[a] | labels_by_user[b])
                condition = 'the union of the two users’ entry intents contains every requested intent'
            else:
                raise ValueError('invalid pair relation')
            answer = [f'({a}, {b})' for a, b in pairs]
            query = phrase('pairs', date_clause=date_clause, condition=condition, labels=canonical(selected))
            query += ' Return each as (smaller ID, larger ID), sorted numerically; do not repeat a pair.'
    elif family == 'small_context_control':
        group = f'group-{uid}'
        count = k.get('records', 8)
        if type(count) is not int or count < 1:
            raise ValueError('records must be a positive integer')
        records = [dict(kind='quantity', group=group if i % 2 == 0 else 'other', value=rng.randrange(1, 100)) for i in range(count)]
        answer = sum(r['value'] for r in records[::2])
        k['query_params'] = dict(group=group)
        query = phrase(family, group=group)
    else:
        symbol = f'compute_{uid}'
        code_files = {
            'core.py': f'def {symbol}(x):\n    return x + 1\n',
            'app.py': f'from core import {symbol}\ndef run(x):\n    return {symbol}(x)\n',
            'settings.py': f'LIMIT_{uid.upper()} = {rng.randrange(100, 1000)}\n',
        }
        operation = k.get('repo_query_type', rng.choice(['definition', 'callers', 'config']))
        if operation == 'definition':
            answer = 'core.py'
        elif operation == 'callers':
            answer = ['app.py:run']
        elif operation == 'config':
            symbol = f'LIMIT_{uid.upper()}'
            answer = code_files['settings.py'].split('=')[1].strip()
        else:
            raise ValueError('invalid repo query type')
        query = phrase(operation, symbol=symbol)
        k['query_params'] = dict(operation=operation, symbol=symbol)
        file_count = k.get('files', 16)
        if file_count < 3:
            raise ValueError('repo requires at least three files')
        for i in range(file_count - 3):
            code_files[f'utils_{i}.py'] = f'def helper_{i}(value):\n    return value * {rng.randrange(2, 9)}\n'
        padding = max(0, k['target_chars'] - sum(len(code) for code in code_files.values()))
        per_file = padding // file_count + 1
        context = []
        for path, code in code_files.items():
            note = f'# Maintenance note {rng.getrandbits(64):016x}: independent utility module.\n'
            code += (note * (per_file // len(note) + 1))
            context.append(f'# File: {path}\n```python\n{code}\n```')
        rng.shuffle(context)
        k['encoding'] = 'markdown'
    if family != 'repo_qa':
        rng.shuffle(records)
        context = render_records(records, encoding=k['encoding'], structure=k['structure'], chunk_chars=k['chunk_chars'])
        length = len(context) if isinstance(context, str) else sum(map(len, context))
        if length < k['target_chars']:
            # Dense auto-sized contexts need no filler; explicit small instances
            # and sparse families receive unrelated archival records.
            while length < k['target_chars']:
                record = dict(kind='note', text=f'Archive {rng.getrandbits(64):016x}: station logs normal weather and routine maintenance.')
                records.append(record)
                length += len(render_records([record], encoding=k['encoding'], structure='str'))
            rng.shuffle(records)
            context = render_records(records, encoding=k['encoding'], structure=k['structure'], chunk_chars=k['chunk_chars'])
    if family == 'small_context_control' and (len(context) if isinstance(context, str) else sum(map(len, context))) >= k['direct_read_max_chars']:
        raise ValueError('rendered small context exceeds direct-read limit')
    identity = dict(family=family, knobs=k, seed=spec.seed, split=spec.split)
    task_id = family + '-' + digest(canonical(identity))[:20]
    if not refs:
        refs = [source_ref('rlm-opsd/synthetic-v1', 'v1', task_id, canonical(context))]
    tags = TAGS[family] + ([] if family == 'small_context_control' else ['large_context'])
    answer_type = 'list_f1' if isinstance(answer, list) else 'numeric' if isinstance(answer, int) else 'exact'
    return Task(task_id=task_id, family=family, split=spec.split, context=context, query=query,
                answer=answer, answer_type=answer_type, knobs=k, seed=spec.seed, source=source,
                source_refs=refs, tags=tags, domain='code' if family == 'repo_qa' else 'long_context')
