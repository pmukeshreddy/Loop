"""Deterministic repository facts: symbols, internal imports, test coverage map."""
import ast
from collections import defaultdict
import difflib


def module_name(path, pythonpath):
    for root in sorted(pythonpath, key=len, reverse=True):
        prefix = '' if root == '.' else root.rstrip('/') + '/'
        if path.startswith(prefix) and path.endswith('.py'):
            dotted = path[len(prefix):-3].replace('/', '.')
            return dotted[:-9] if dotted.endswith('.__init__') else dotted
    return None


def symbols(tree):
    """Map qualname -> (first line, last line) for every function and class."""
    found = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                found[name] = (start, child.end_lineno)
                visit(child, name + '.')
    visit(tree, '')
    return found


def _imports(tree, current, known):
    edges = set()
    package = current.rsplit('.', 1)[0] if '.' in current else current
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = package.split('.')
                anchor = parts[:len(parts) - node.level + 1] if node.level > 1 else parts
                base = '.'.join(anchor + ([base] if base else []))
            # `from pkg import sub` depends on pkg.sub when it is a module, else on pkg.
            names = [f'{base}.{a.name}' if f'{base}.{a.name}' in known else base for a in node.names]
        else:
            continue
        for name in names:
            while name and name not in known:
                name = name.rsplit('.', 1)[0] if '.' in name else ''
            if name and name != current:
                edges.add(name)
    return edges


def repository_facts(spec, documents):
    """Facts over the selected documents; parse failures are recorded, not hidden."""
    parsed, modules, errors = {}, {}, []
    for document in documents:
        if not document.path.endswith('.py'):
            continue
        try:
            parsed[document.path] = ast.parse(document.text)
        except SyntaxError as exc:
            errors.append(dict(path=document.path, error=f'SyntaxError line {exc.lineno}'))
            continue
        name = module_name(document.path, spec.pythonpath)
        if name and document.kind == 'source':
            modules[name] = document.path
    known = set(modules)
    source, tests = [], []
    for document in documents:
        tree = parsed.get(document.path)
        if tree is None:
            continue
        name = module_name(document.path, spec.pythonpath) or document.path
        imports = sorted(_imports(tree, name, known))
        if document.kind == 'source':
            top = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            source.append(dict(path=document.path, module=name, chars=len(document.text), imports=imports,
                               top_level=top, symbols=len(symbols(tree))))
        elif document.kind == 'test':
            count = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test')
                        for n in ast.walk(tree))
            tests.append(dict(path=document.path, chars=len(document.text), imports=imports, test_functions=count))
    imported_by = defaultdict(list)
    for row in source:
        for target in row['imports']:
            imported_by[target].append(row['module'])
    for row in source:
        row['imported_by'] = sorted(imported_by[row['module']])
    docs = [dict(path=d.path, kind=d.kind, chars=len(d.text)) for d in documents if d.kind in ('doc', 'config', 'other')]
    return dict(repo=spec.name, source_modules=source, test_files=tests, other_files=docs, parse_errors=errors,
                totals=dict(documents=len(documents), chars=sum(len(d.text) for d in documents),
                            source_chars=sum(r['chars'] for r in source), test_chars=sum(t['chars'] for t in tests)))


def facts_digest(facts, limit=60000):
    lines = [f"Repository {facts['repo']}: {facts['totals']}"]
    lines.append('\nSource modules (path | chars | imports internal | imported by | top-level symbols):')
    for row in sorted(facts['source_modules'], key=lambda r: -len(r['imported_by'])):
        lines.append(f"- {row['path']} | {row['chars']} | -> {', '.join(row['imports']) or '-'} | <- "
                     f"{', '.join(row['imported_by']) or '-'} | {', '.join(row['top_level'][:40])}")
    lines.append('\nTest files (path | test functions | internal imports):')
    for row in facts['test_files']:
        lines.append(f"- {row['path']} | {row['test_functions']} | {', '.join(row['imports']) or '-'}")
    lines.append('\nOther files: ' + ', '.join(f"{d['path']} ({d['chars']})" for d in facts['other_files'][:200]))
    text = '\n'.join(lines)
    return text[:limit]


def normalize_symbol(text):
    text = str(text).strip().strip('`').strip()
    text = text[2:] if text.startswith('./') else text
    if '::' not in text and ':' in text:
        path, _, name = text.partition(':')
        text = f'{path}::{name}'
    path, _, name = text.partition('::')
    return f'{path.strip()}::{name.strip()}' if name else path.strip()


def diff_symbols(changes):
    """Innermost functions/classes changed between real file versions.

    `changes` holds (path, old_text_or_None, new_text). Hunk headers in model-written
    patches are approximate, so line numbers come from diffing the actual files.
    """
    found = set()
    for path, old, new in changes:
        old_lines, new_lines = (old or '').splitlines(), new.splitlines()
        lines = set()
        for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
            if tag == 'equal':
                continue
            lines.update(range(j1 + 1, j2 + 1) if j2 > j1 else [max(1, j1)])
        if not path.endswith('.py'):
            found.add(f'{path}::<file>')
            continue
        spans = symbols(ast.parse(new))
        for line in lines:
            enclosing = [(end - start, name) for name, (start, end) in spans.items() if start <= line <= end]
            found.add(f'{path}::{min(enclosing)[1]}' if enclosing else f'{path}::<module>')
    return sorted(found)
