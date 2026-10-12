"""Check that a reference execution actually exhibits a task's intended behaviors.

Runtime sub-call logs are authoritative for whether and how large sub-calls
were. Code facts come from a small provenance analysis over each REPL block:
which names derive from `context`, which derive from `llm_query` results, and
which names a later turn reuses. Call counts are evidence that a behavior
occurred, never a success measure. Detector values (D1–D19) are recorded for
audit only.
"""
import ast
import builtins
import re
import warnings

from rlm_opsd.detectors import DetectorConfig, analyze_trajectory
from rlm_opsd.harness.protocol import parse_turn

from .models import FAMILIES

_IGNORED = set(dir(builtins)) | {'context', 'llm_query', 'llm_query_batched', 're', 'json', 'collections',
                                 'difflib', 'itertools', 'functools', 'textwrap', 'ast', 'math', 'os', 'sys'}
_SUBCALLS = {'llm_query', 'llm_query_batched'}
# Rebuilding, importing, executing or testing repository code bypasses the
# context investigation these tasks exist to teach. Detected from the AST, so
# strings, comments and log keys that mention these names do not count.
_EXEC_MODULES = {'subprocess', 'pytest', 'runpy', 'importlib', 'multiprocessing', 'tempfile', 'shutil', 'pty'}
_EXEC_BUILTINS = {'exec', 'eval', 'compile', '__import__'}
_OS_EXEC = re.compile(r'^(?:system|popen|exec\w*|spawn\w*|makedirs|mkdir|fork)$')
_WRITE_ATTRS = {'write_text', 'write_bytes', 'mkdir', 'touch', 'symlink_to'}


def execution_constructs(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            found.update(n.split('.')[0] for n in names if n.split('.')[0] in _EXEC_MODULES)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _EXEC_BUILTINS:
                found.add(func.id)
            elif isinstance(func, ast.Name) and func.id == 'open':
                mode = node.args[1] if len(node.args) > 1 else next(
                    (k.value for k in node.keywords if k.arg == 'mode'), None)
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and set(mode.value) & set('wax+'):
                    found.add('open-for-write')
            elif isinstance(func, ast.Attribute):
                base = func.value.id if isinstance(func.value, ast.Name) else ''
                if base == 'os' and _OS_EXEC.match(func.attr):
                    found.add(f'os.{func.attr}')
                elif func.attr in _WRITE_ATTRS:
                    found.add(func.attr)
                elif base == 'path' and isinstance(func.value, ast.Name) and func.attr in ('insert', 'append'):
                    found.add('sys.path')
                elif isinstance(func.value, ast.Attribute) and func.value.attr == 'path' and \
                        isinstance(func.value.value, ast.Name) and func.value.value.id == 'sys':
                    found.add('sys.path')
    return found


_SEARCH_ATTRS = {'search', 'findall', 'finditer', 'match', 'fullmatch', 'find', 'rfind', 'index', 'count',
                 'startswith', 'endswith', 'splitlines', 'split', 'partition'}


def _loads(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _targets(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}


def _calls(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in _SUBCALLS]


class _Block(ast.NodeVisitor):
    """Provenance over one block, given names derived in earlier blocks."""

    def __init__(self, from_context, from_subcalls):
        self.ctx, self.sub = from_context, from_subcalls
        self.sites, self.searches, self.loop = [], 0, 0
        self.stores, self.loads = {}, {}

    def derived(self, node):
        names = _loads(node)
        return bool(names & (self.ctx | {'context'})), bool(names & self.sub) or bool(_calls(node))

    def flow(self, targets, value):
        from_ctx, from_sub = self.derived(value)
        for name in targets:
            (self.ctx.add if from_ctx else self.ctx.discard)(name)
            (self.sub.add if from_sub else self.sub.discard)(name)

    def flow_into_container(self, target, value):
        """`d[k] = v` / `obj.attr = v` partially update `d` / `obj`: add provenance, never clear it."""
        while isinstance(target, (ast.Subscript, ast.Attribute)):
            target = target.value
        if isinstance(target, ast.Name):
            from_ctx, from_sub = self.derived(value)
            if from_ctx:
                self.ctx.add(target.id)
            if from_sub:
                self.sub.add(target.id)

    def visit_Assign(self, node):
        self.generic_visit(node)
        self.flow(set().union(*(_targets(t) for t in node.targets
                                if not isinstance(t, (ast.Subscript, ast.Attribute)))), node.value)
        for target in node.targets:
            if isinstance(target, (ast.Subscript, ast.Attribute)):
                self.flow_into_container(target, node.value)
        self._stored(node.value)

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        if node.value is not None:
            self.flow(_targets(node.target), node.value)
            self._stored(node.value)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        from_ctx, from_sub = self.derived(node.value)
        for name in _targets(node.target):
            if from_ctx:
                self.ctx.add(name)
            if from_sub:
                self.sub.add(name)
        self._stored(node.value)

    def _stored(self, value):
        for call in _calls(value):
            for site in self.sites:
                if site['node'] is call:
                    site['stored'] = True

    def visit_For(self, node):
        self.flow(_targets(node.target), node.iter)
        self.visit(node.iter)
        self.loop += 1
        for child in node.body + node.orelse:
            self.visit(child)
        self.loop -= 1

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.loop += 1
        self.generic_visit(node)
        self.loop -= 1

    def _comprehension(self, node):
        for generator in node.generators:
            self.flow(_targets(generator.target), generator.iter)
        self.loop += 1
        self.generic_visit(node)
        self.loop -= 1

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comprehension

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in _SUBCALLS:
            argument = ast.Tuple(elts=list(node.args) + [k.value for k in node.keywords], ctx=ast.Load())
            from_ctx, _ = self.derived(argument)
            whole = any(isinstance(a, ast.Name) and a.id == 'context' for a in node.args) or any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == 'join'
                and any(isinstance(a, ast.Name) and a.id == 'context' for a in c.args) for c in ast.walk(argument))
            self.sites.append(dict(node=node, context=from_ctx, whole=whole, stored=False,
                                   in_loop=self.loop > 0 or node.func.id.endswith('_batched')))
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else ''
        if attr in _SEARCH_ATTRS and self.derived(node)[0]:
            self.searches += 1
        self.generic_visit(node)
        if attr in ('append', 'extend', 'add', 'update') and isinstance(node.func.value, ast.Name) and node.args:
            from_ctx, from_sub = self.derived(node.args[0])
            if from_ctx:
                self.ctx.add(node.func.value.id)
            if from_sub:
                self.sub.add(node.func.value.id)
            self._stored(node.args[0])

    def visit_Compare(self, node):
        if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops) and self.derived(node)[0]:
            self.searches += 1
        self.generic_visit(node)

    def visit_Name(self, node):
        table = self.stores if isinstance(node.ctx, ast.Store) else self.loads
        table.setdefault(node.id, []).append((node.lineno, node.col_offset))

    def reads_before_write(self, tree):
        """Names whose first use in this block is a read (true cross-turn reuse)."""
        local = {n.id for c in ast.walk(tree) if isinstance(c, ast.comprehension) for n in ast.walk(c.target)
                 if isinstance(n, ast.Name)}
        result = set()
        for name, loads in self.loads.items():
            stores = self.stores.get(name, [])
            if name not in local and (not stores or min(loads) < min(stores)):
                result.add(name)
        return result


def execution_facts(trace, *, context_total, hand_copy_min_chars):
    turns = trace['turns']
    from_context, from_subcalls = set(), set()
    first_store, reused, sites, searches, prints_whole = {}, set(), [], 0, 0
    last_store = {}
    loads_after = {}
    blocks = []
    for index, turn in enumerate(turns):
        for code in turn.get('code_blocks', []):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', SyntaxWarning)  # model regexes in non-raw strings
                    tree = ast.parse(code)
            except (SyntaxError, ValueError, RecursionError):
                continue
            visitor = _Block(from_context, from_subcalls)
            visitor.visit(tree)
            sites += visitor.sites
            searches += visitor.searches
            prints_whole += sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                and n.func.id == 'print' and any(isinstance(a, ast.Name) and a.id == 'context'
                                                                 for a in n.args))
            for name in visitor.reads_before_write(tree):
                if name in first_store and first_store[name] < index and name not in _IGNORED:
                    reused.add(name)
            for name, positions in visitor.stores.items():
                first_store.setdefault(name, index)
                last_store[name] = (index, max(positions))
            for name, positions in visitor.loads.items():
                loads_after.setdefault(name, []).extend((index, p) for p in positions)
            blocks.append((index, code, tree))
    subcalls = [c for t in turns for c in t.get('subcalls', [])]
    execution = sorted(set().union(*(execution_constructs(tree) for _, _, tree in blocks)))
    finish = None
    for turn in turns:
        parsed = parse_turn(turn.get('assistant_text', ''))
        if parsed.finish_type:
            finish = (parsed.finish_type, parsed.finish_argument)
    checked = computed = False
    if finish and finish[0] == 'FINAL_VAR' and finish[1] in last_store:
        name = finish[1]
        where = last_store[name]
        checked = any((turn, pos) > where for turn, pos in loads_after.get(name, []))
        # Computed from evidence: the final value derives, through code, from `context`
        # or sub-call results. A literal retyped from printed output does not count.
        computed = name in from_context or name in from_subcalls
    literals = [str(n.value) for _, _, tree in blocks for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    earlier_output = ''.join(t.get('stdout_truncated', '') for t in turns)
    hand_copied = sum(1 for literal in literals if len(literal) >= hand_copy_min_chars and literal in earlier_output)
    whole_runtime = sum(1 for c in subcalls if context_total and c['prompt_chars'] >= 0.9 * context_total)
    return dict(
        turns=len(turns), code_blocks=len(blocks), context_searches=searches, whole_context_prints=prints_whole,
        subcalls=len(subcalls), subcall_errors=sum(bool(c.get('error')) for c in subcalls),
        subcall_max_prompt_chars=max((c['prompt_chars'] for c in subcalls), default=0),
        subcall_sites=len(sites), subcall_sites_on_context=sum(s['context'] and not s['whole'] for s in sites),
        subcall_sites_whole_context=sum(s['whole'] for s in sites) + whole_runtime,
        subcall_sites_in_loop=sum(s['in_loop'] for s in sites), subcall_results_stored=sum(s['stored'] for s in sites),
        subcall_results_in_final=bool(finish and finish[0] == 'FINAL_VAR' and finish[1] in from_subcalls),
        reused_variables=sorted(reused), hand_copied_literals=hand_copied,
        repository_execution=execution,
        finish=finish[0] if finish else None, final_variable_checked=checked, final_computed=computed,
        final_error=trace['final'].get('error'))


def detector_config(practice, harness):
    return DetectorConfig(probe_max_chars=practice['probe_max_chars'], dump_threshold=practice['dump_threshold'],
                          read_threshold=practice['read_threshold'], many_hits=practice['many_hits'],
                          subcall_max_chars=practice['subcall_max_chars'], min_batch_chars=practice['min_batch_chars'],
                          max_subcalls_expected=dict.fromkeys(FAMILIES, harness.max_subcalls),
                          hand_copy_min_chars=practice['hand_copy_min_chars'],
                          dense_coverage_min=practice['dense_coverage_min'])


def check_behaviors(trace, intended, *, context_chars, practice, harness, direct_read_max_chars):
    facts = execution_facts(trace, context_total=context_chars, hand_copy_min_chars=practice['hand_copy_min_chars'])
    detectors = analyze_trajectory({**trace, 'tags': []}, detector_config(practice, harness))
    large = context_chars >= practice['large_context_min_chars']
    clean_finish = facts['finish'] in ('FINAL', 'FINAL_VAR') and not facts['final_error']
    checks = {
        'inspect_locate': (large and facts['context_searches'] > 0 and facts['whole_context_prints'] == 0,
                           f"context {context_chars} chars; {facts['context_searches']} code searches over context; "
                           f"{facts['whole_context_prints']} whole-context prints"),
        'chunked_subcalls': (facts['subcalls'] - facts['subcall_errors'] > facts['subcall_errors']
                             and facts['subcall_sites_on_context'] > 0 and facts['subcall_sites_whole_context'] == 0
                             and facts['subcall_max_prompt_chars'] <= practice['subcall_max_chars'],
                             f"{facts['subcalls']} sub-calls ({facts['subcall_errors']} failed); {facts['subcall_sites_on_context']} call sites on selected "
                             f"context, {facts['subcall_sites_whole_context']} on the whole context; max prompt "
                             f"{facts['subcall_max_prompt_chars']} chars"),
        'recursive_decomposition': (facts['subcalls'] - facts['subcall_errors'] >= practice['min_subcalls_decomposition']
                                    and facts['subcall_results_stored'] > 0
                                    and facts['subcall_results_in_final'],
                                    f"{facts['subcalls']} sub-calls ({facts['subcall_errors']} failed); results stored at {facts['subcall_results_stored']} "
                                    f"sites; sub-call results reach the final answer: {facts['subcall_results_in_final']}"),
        'persistent_state': (facts['turns'] >= practice['min_turns_persistent_state']
                             and len(facts['reused_variables']) > 0 and facts['hand_copied_literals'] == 0,
                             f"{facts['turns']} turns; variables reused across turns: "
                             f"{facts['reused_variables'][:12]}; hand-copied literals {facts['hand_copied_literals']}"),
        'combine_verify_finish': (clean_finish and facts['finish'] == 'FINAL_VAR' and facts['final_computed']
                                  and facts['final_variable_checked'],
                                  f"finish {facts['finish']}; final value computed in code: {facts['final_computed']}; "
                                  f"inspected after construction: {facts['final_variable_checked']}"),
        'direct_solve': (context_chars < direct_read_max_chars and facts['subcalls'] == 0 and clean_finish,
                         f"context {context_chars} chars; {facts['subcalls']} sub-calls"),
    }
    results = {name: dict(established=bool(checks[name][0]), evidence=checks[name][1]) for name in intended}
    established = [name for name in intended if results[name]['established']]
    tags = []
    if large and 'direct_solve' not in established:
        tags.append('large_context')
    if 'inspect_locate' in established:
        tags.append('sparse')
        if detectors['detectors'].get('D6') is True:
            tags.append('chained_search')
    coverage = detectors.get('coverage_lower_bound')
    if {'chunked_subcalls', 'recursive_decomposition'} & set(established) and facts['subcall_sites_in_loop'] \
            and coverage is not None and coverage > practice['dense_coverage_min']:
        tags.append('needs_subcalls')
    if 'combine_verify_finish' in established:
        tags.append('aggregate_in_code')
    if facts['finish'] == 'FINAL_VAR':
        tags.append('output_in_variable')
    if 'direct_solve' in established:
        tags.append('small_context')
    return dict(results=results, established=established, facts=facts, tags=tags,
                detectors=detectors['detectors'], coverage_lower_bound=coverage)
