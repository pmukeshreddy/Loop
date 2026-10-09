"""Answer oracles read serialized context, never Task.answer or generator state."""
import ast
from collections import Counter, defaultdict
from itertools import combinations
import re

from .codec import parse_records


def repo_files(context):
    if not isinstance(context, list):
        raise ValueError('repo context must be a list of file strings')
    files = {}
    for document in context:
        match = re.fullmatch(r'# File: ([^\n]+)\n```python\n(.*?)\n```\s*', document, re.S)
        if not match or match[1] in files:
            raise ValueError('invalid or duplicate repository file')
        files[match[1]] = ast.parse(match[2])
    return files


def verify_answer(task, corpus=None):
    params = task.knobs['query_params']
    if task.family == 'repo_qa':
        files = repo_files(task.context)
        symbol = params['symbol']
        if params['operation'] == 'definition':
            matches = [path for path, tree in files.items() if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
                for node in tree.body)]
            if len(matches) != 1:
                raise ValueError('definition must be unique')
            return matches[0]
        if params['operation'] == 'callers':
            return sorted(f'{path}:{node.name}' for path, tree in files.items()
                          for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                          and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                                  and call.func.id == symbol for call in ast.walk(node)))
        if params['operation'] == 'config':
            values = [ast.literal_eval(node.value) for tree in files.values() for node in tree.body
                      if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets)]
            if len(values) != 1:
                raise ValueError('config key must be unique')
            return str(values[0])
        raise ValueError('unknown repo query operation')
    records = parse_records(task.context, task.knobs['encoding'])
    if task.family == 'sparse_retrieval':
        facts = defaultdict(list)
        for record in records:
            if record['kind'] == 'fact':
                facts[record['key']].append(record['value'])
        values = []
        for key in params['keys']:
            if len(facts[key]) != 1:
                raise ValueError('needle must occur exactly once')
            values.append(facts[key][0])
        return values[0] if len(values) == 1 else values
    if task.family == 'multi_hop':
        current = params['start']
        for _ in range(params['hops']):
            links = [r['target'] for r in records if r['kind'] == 'link' and r['key'] == current]
            if len(links) != 1:
                raise ValueError('broken or ambiguous chain')
            current = links[0]
        answers = [r['value'] for r in records if r['kind'] == 'terminal' and r['key'] == current]
        if len(answers) != 1:
            raise ValueError('broken chain terminal')
        return answers[0]
    if task.family == 'small_context_control':
        return sum(r['value'] for r in records if r['kind'] == 'quantity' and r['group'] == params['group'])
    if corpus is None:
        raise ValueError('classification source annotations required for verification')
    entries = [(r, corpus.label_for(r['text'])) for r in records if r['kind'] == 'entry']
    after = params.get('after')
    entries = [(r, label) for r, label in entries if after is None or r['date'] > after]
    if task.family == 'linear_aggregation':
        counts = Counter(label for _, label in entries)
        if params['operation'] == 'count':
            return counts[params['label']]
        if params['operation'] == 'most_frequent':
            return min(counts, key=lambda label: (-counts[label], label)) if counts else 'NONE'
        raise ValueError('unknown aggregation operation')
    if task.family == 'quadratic_pairs':
        by_user = defaultdict(set)
        for record, label in entries:
            by_user[record['user']].add(label)
        wanted = set(params['labels'])
        result = []
        for a, b in combinations(sorted(by_user), 2):
            if params['relation'] == 'both_have_any':
                valid = bool(by_user[a] & wanted) and bool(by_user[b] & wanted)
            elif params['relation'] == 'cover_labels':
                valid = wanted <= (by_user[a] | by_user[b])
            else:
                raise ValueError('unknown pair relation')
            if valid:
                result.append(f'({a}, {b})')
        return result
    raise ValueError(f'unknown task family: {task.family}')
