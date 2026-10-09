"""Bounded, non-executing abstract interpretation of REPL code.

Only literal arithmetic/geometry is evaluated. Unsupported control flow is
reported explicitly; no imports, user functions, or trajectory code are run.
"""
import ast
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Value:
    context: bool = False
    whole: bool = False
    ranges: tuple | None = ()
    size: int | None = None
    kind: str = 'unknown'
    constant: object = None
    items: tuple | None = None
    searches: frozenset = frozenset()
    position: tuple | None = None
    calls: frozenset = frozenset()
    computed: bool = False
    count_of: frozenset = frozenset()


def union_ranges(ranges):
    merged = []
    for lo,hi in sorted(set(ranges)):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0],max(hi,merged[-1][1]))
        else:
            merged.append((lo,hi))
    return tuple(merged)


def combine(*values, **changes):
    ranges = None if any(v.ranges is None for v in values) else union_ranges(r for v in values for r in v.ranges)
    return replace(Value(context=any(v.context for v in values), whole=any(v.whole for v in values), ranges=ranges,
                         searches=frozenset(s for v in values for s in v.searches),
                         calls=frozenset(c for v in values for c in v.calls),
                         computed=any(v.computed for v in values)), **changes)


def literal(value):
    return Value(constant=value, kind=type(value).__name__, size=len(value) if isinstance(value, str) else None)


class Extractor:
    MAX_ITEMS = 1024
    MAX_NODES = 20000
    MAX_STEPS = 50000
    MAX_SOURCE_CHARS = 100000

    def __init__(self, metadata):
        self.metadata = metadata or {}
        self.total = self.metadata.get('context_total_length')
        ranges = None if self.total is None else ((0, self.total),)
        ctx = Value(context=True, whole=True, ranges=ranges, size=self.total, kind=self.metadata.get('context_type', 'unknown'))
        if ctx.kind == 'list' and len(self.metadata['context_lengths']) <= self.MAX_ITEMS:
            offset, items = 0, []
            for length in self.metadata['context_lengths']:
                items.append(Value(context=True, ranges=((offset, offset + length),), size=length, kind='str'))
                offset += length
            ctx = replace(ctx, items=tuple(items))
        self.env = {'context': ctx}
        self.defined = {}
        self.regex_names = {'re'}
        self.regex_functions = set()
        self.blocks, self.events, self.searches, self.calls, self.prints = [], [], [], [], []
        self.unknown, self.verified = [], set()
        self.turn = self.loop_depth = self.steps = 0
        self.block = None

    def uncertain(self, reason):
        message = f'turn {self.turn}: {reason}'
        if message not in self.unknown:
            self.unknown.append(message)
        if reason not in self.block['uncertainties']:
            self.block['uncertainties'].append(reason)

    def event(self, kind, value, **details):
        event = dict(kind=kind, turn=self.turn, block=len(self.blocks)-1, order=len(self.events),
                     whole=value.whole, context=value.context, size=value.size,
                     ranges=value.ranges, searches=sorted(value.searches), **details)
        self.events.append(event)
        if kind in ('read', 'print', 'probe', 'scan', 'iteration'):
            self.block['accesses'].append(event)
        if kind == 'read':
            self.block['reads'].append(event)
        return event

    def read(self, value):
        if value.context:
            self.event('read', value, window=bool(value.position))
            if value.position:
                self.verified.update(value.searches)
        return value

    def assign(self, target, value):
        if isinstance(target, ast.Name):
            self.env[target.id] = value
            self.defined[target.id] = self.turn
            self.block['assigned'].append(target.id)
            for call in value.calls:
                self.calls[call]['stored'] = True
        elif isinstance(target, (ast.Tuple, ast.List)):
            for i, item in enumerate(target.elts):
                self.assign(item, value.items[i] if value.items is not None and i < len(value.items) else replace(value, items=None, constant=None))
        elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            name = target.value.id
            self.assign(target.value, combine(self.env.get(name, Value()), value, computed=True))
        else:
            self.uncertain('unsupported assignment target')

    def expr(self, node, mode='read'):
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise OverflowError('AST analysis step limit')
        if node is None:
            return Value()
        if isinstance(node, ast.Constant):
            return literal(node.value)
        if isinstance(node, ast.Name):
            if self.defined.get(node.id, self.turn) < self.turn:
                self.block['reused'].append(node.id)
            return self.env.get(node.id, Value())
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            items = tuple(self.expr(n, mode) for n in node.elts)
            return combine(*items, kind='list', items=items)
        if isinstance(node, ast.Dict):
            items = tuple(self.expr(n, mode) for n in node.values)
            return combine(*items, kind='dict', items=items)
        if isinstance(node, ast.UnaryOp):
            val = self.expr(node.operand, mode)
            if isinstance(val.constant, (int, float)) and isinstance(node.op, (ast.USub, ast.UAdd)):
                return replace(val, constant=-val.constant if isinstance(node.op, ast.USub) else val.constant)
            if isinstance(node.op, ast.Not) and val.constant is not None:
                return literal(not val.constant)
            return replace(val, constant=None, computed=True)
        if isinstance(node, ast.BinOp):
            a, b = self.expr(node.left, mode), self.expr(node.right, mode)
            val = combine(a, b, computed=True)
            if a.position and type(b.constant) is int and isinstance(node.op, (ast.Add, ast.Sub)):
                val = replace(val, position=(a.position[0], a.position[1] + b.constant * (-1 if isinstance(node.op, ast.Sub) else 1)))
            if isinstance(node.op, ast.Add) and a.size is not None and b.size is not None:
                val = replace(val, size=a.size+b.size)
            if type(a.constant) is int and type(b.constant) is int:
                try:
                    if isinstance(node.op, ast.Add): c = a.constant+b.constant
                    elif isinstance(node.op, ast.Sub): c = a.constant-b.constant
                    elif isinstance(node.op, ast.Mult): c = a.constant*b.constant
                    elif isinstance(node.op, ast.FloorDiv): c = a.constant//b.constant
                    else: c = None
                    if c is not None and abs(c).bit_length() <= 256:
                        val = replace(val, constant=c)
                except ZeroDivisionError:
                    pass
            return val
        if isinstance(node, ast.Subscript):
            base = self.expr(node.value, 'ref')
            if isinstance(node.slice, ast.Slice):
                lo, hi, step = (self.expr(n, 'ref') for n in (node.slice.lower, node.slice.upper, node.slice.step))
                bounds_known = all(n is None or type(v.constant) is int for n,v in ((node.slice.lower,lo),(node.slice.upper,hi),(node.slice.step,step)))
                position = lo.position if lo.position and hi.position and lo.position[0] == hi.position[0] else None
                val = replace(base, whole=False, ranges=None if base.context else (), size=None, items=None, constant=None,
                              searches=base.searches | lo.searches | hi.searches, position=position, computed=True)
                length = len(base.items) if base.items is not None else base.size if base.kind == 'str' else None
                if bounds_known and length is not None and step.constant != 0:
                    start, stop, stride = slice(lo.constant, hi.constant, step.constant).indices(length)
                    if base.items is not None:
                        items = base.items[start:stop:stride] if stride > 0 else base.items[slice(lo.constant,hi.constant,step.constant)]
                        val = combine(*items, context=base.context, kind=base.kind, items=items,
                                      size=sum(x.size for x in items) if all(x.size is not None for x in items) else None,
                                      searches=val.searches, computed=True)
                    elif stride == 1 and base.ranges is not None and len(base.ranges) == 1:
                        origin = base.ranges[0][0]
                        val = replace(val, ranges=((origin+start,origin+max(start,stop)),), size=max(0,stop-start))
                    elif not base.context:
                        val = replace(val, size=len(range(start,stop,stride)))
                elif position:
                    val = replace(val, size=max(0, hi.position[1]-lo.position[1]))
            else:
                index = self.expr(node.slice, 'ref')
                if base.items is not None and type(index.constant) is int and -len(base.items) <= index.constant < len(base.items):
                    val = base.items[index.constant]
                else:
                    val = replace(base, whole=False, ranges=None if base.context else (), size=1 if base.kind == 'str' else None,
                                  items=None, constant=None, searches=base.searches | index.searches, computed=True)
            if val.context and val.ranges == ((0, self.total),) and self.total is not None:
                val = replace(val, whole=True)
            return self.read(val) if mode == 'read' else val
        if isinstance(node, ast.Call):
            return self.call(node, mode)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            return self.comprehension(node, mode)
        if isinstance(node, ast.Compare):
            values = [self.expr(node.left, 'ref')] + [self.expr(n, 'ref') for n in node.comparators]
            for i, op in enumerate(node.ops):
                if isinstance(op, (ast.In, ast.NotIn)) and values[i+1].context:
                    return self.search(node, values[i+1], values[i], node.left, 'in')
            return combine(*values, computed=True)
        if isinstance(node, ast.JoinedStr):
            return combine(*(self.expr(n.value if isinstance(n, ast.FormattedValue) else n, mode) for n in node.values), computed=True)
        if isinstance(node, ast.Attribute):
            return self.expr(node.value, mode)
        if isinstance(node, (ast.BoolOp, ast.IfExp)):
            self.uncertain('dynamic conditional expression')
            return Value()
        self.uncertain(f'unsupported expression: {type(node).__name__}')
        return Value()

    def search(self, node, source, pattern, pattern_node, method):
        sid = len(self.searches)
        event = self.event('search', source, id=sid, method=method,
                           pattern=repr(pattern.constant) if pattern.constant is not None else None,
                           pattern_expression=ast.dump(pattern_node, include_attributes=False) if pattern_node is not None else method,
                           chained=bool(pattern.searches), hit_count=None)
        self.searches.append(event)
        self.block['searches'].append(event)
        positional = method in ('find', 'index')
        scalar = positional or method in ('count','in')
        return replace(source, whole=False, ranges=None, size=None, items=None, constant=None,
                       context=not scalar and source.context,
                       searches=source.searches | {sid}, position=(sid,0) if positional else None,
                       kind='position' if positional else 'matches', computed=True)

    def call(self, node, mode):
        name = node.func.id if isinstance(node.func, ast.Name) else ''
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else ''
        base = self.expr(node.func.value, 'ref') if attr else Value()
        if name and name in self.defined:
            self.uncertain(f'unsupported or shadowed callable: {name}')
            return Value()
        # Metadata reads do not count as reading the underlying content.
        if name in ('len', 'type'):
            values = [self.expr(n, 'meta') for n in node.args]
            value = values[0] if values else Value()
            if value.context:
                self.event('probe', value, operation=name)
            c = (len(value.items) if value.items is not None else value.size) if name == 'len' else None
            return Value(constant=c, computed=True, searches=value.searches, calls=value.calls,
                         count_of=value.searches if name == 'len' else frozenset())
        if name == 'print':
            values = [self.expr(n) for n in node.args]
            self.prints.append(dict(turn=self.turn, values=values))
            for value in values:
                if value.context:
                    self.event('print', value, window=bool(value.position))
                    self.read(value)
            return Value()
        if name in ('llm_query', 'llm_query_batched'):
            args = [self.expr(n) for n in node.args]
            args += [self.expr(n.value) for n in node.keywords]
            value = combine(*args)
            if len(args) == 1:
                value = args[0]
            cid = len(self.calls)
            call = self.event('subcall', value, id=cid, in_loop=self.loop_depth > 0 or name.endswith('_batched'), stored=False)
            self.calls.append(call)
            self.block['subcalls'].append(call)
            if value.searches:
                self.verified.update(value.searches)
            return Value(calls=frozenset({cid}), searches=value.searches, computed=True, kind='str')
        is_re = attr and isinstance(node.func.value, ast.Name) and node.func.value.id in self.regex_names
        if ((is_re or name in self.regex_functions) and (attr or name) in ('findall','finditer','search','match','fullmatch','split')):
            args = [self.expr(n, 'ref') for n in node.args]
            if len(args) >= 2 and args[1].context:
                return self.search(node,args[1],args[0],node.args[0],attr or name)
            return combine(*args, computed=True)
        if attr in ('find','index','count','split','splitlines') and base.context:
            pattern = self.expr(node.args[0], 'ref') if node.args else Value()
            return self.search(node,base,pattern,node.args[0] if node.args else None,attr)
        args = [self.expr(n, mode) for n in node.args]
        args += [self.expr(n.value, mode) for n in node.keywords]
        if name == 'range' and all(type(v.constant) is int for v in args) and 1 <= len(args) <= 3:
            try:
                sequence = range(*(v.constant for v in args))
                if len(sequence) <= self.MAX_ITEMS:
                    return Value(items=tuple(literal(v) for v in sequence))
            except (ValueError, OverflowError):
                pass
            self.uncertain('unresolved or oversized range')
        if name == 'enumerate' and args and args[0].items is not None:
            return replace(args[0], items=tuple(Value(items=(literal(i),v)) for i,v in enumerate(args[0].items)))
        if name in ('min','max'):
            positional = [v for v in args if v.position]
            if len(positional) == 1:
                return positional[0]
            if args and all(type(v.constant) is int for v in args):
                return literal((min if name == 'min' else max)(v.constant for v in args))
        if attr in ('start','end') and base.searches:
            return replace(base, context=False, ranges=(), position=(min(base.searches),0), kind='position')
        if attr in ('append','extend') and isinstance(node.func.value, ast.Name):
            value = combine(base, *args, computed=True)
            # Preserve known collection length for subsequent metadata arithmetic.
            if base.items is not None and attr == 'append' and len(args) == 1:
                if len(base.items) < self.MAX_ITEMS:
                    value = replace(value, items=base.items + (args[0],), kind='list')
                else:
                    self.uncertain('collection item limit')
            self.assign(node.func.value, value)
            return Value()
        if attr in ('strip','lstrip','rstrip','lower','upper','replace','join','values','items','groups','group','split','splitlines') or name in ('sum','sorted','list','tuple','set','dict','str','int','float','Counter'):
            return combine(base, *args, computed=True)
        value = combine(base, *args)
        self.uncertain(f'unsupported call: {name or attr or "callable"}')
        return replace(value, ranges=None if value.context else (), size=None, computed=True)

    def iterate(self, value):
        if value.context:
            self.event('iteration', value)
        if value.items is not None and len(value.items) <= self.MAX_ITEMS:
            return value.items
        self.uncertain('unresolved iteration')
        return None

    def comprehension(self, node, mode):
        saved_env, saved_defined = self.env.copy(), self.defined.copy()
        values, filtered = [], []
        def visit(level):
            if level == len(node.generators):
                values.append(self.expr(node.value if isinstance(node,ast.DictComp) else node.elt, mode))
                return
            gen = node.generators[level]
            source = self.expr(gen.iter, 'ref')
            items = self.iterate(source)
            if items is None:
                return
            for value in items:
                self.assign(gen.target, value)
                skip = False
                for condition in gen.ifs:
                    test = self.expr(condition)
                    if test.constant is not None:
                        if not test.constant:
                            skip = True
                            break
                    else:
                        # The predicate executes; its truth and selected elements
                        # cannot be recovered from a trajectory's metadata.
                        filtered.append(test)
                        skip = True
                        elt = node.value if isinstance(node,ast.DictComp) else node.elt
                        if any(isinstance(n,ast.Call) for n in ast.walk(elt)):
                            self.uncertain('call inside unresolved comprehension filter')
                if skip:
                    continue
                visit(level+1)
        self.loop_depth += 1
        try:
            visit(0)
        finally:
            self.loop_depth -= 1
            self.env, self.defined = saved_env, saved_defined
        return combine(*values, *filtered, items=None if filtered else tuple(values), computed=True)

    def statements(self, statements):
        for node in statements:
            self.steps += 1
            if self.steps > self.MAX_STEPS:
                raise OverflowError('AST analysis step limit')
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = self.expr(node.value)
                for target in node.targets if isinstance(node,ast.Assign) else [node.target]:
                    self.assign(target,value)
            elif isinstance(node, ast.AugAssign):
                value = combine(self.expr(node.target),self.expr(node.value),computed=True)
                self.assign(node.target,value)
            elif isinstance(node, ast.Expr):
                self.expr(node.value)
            elif isinstance(node, ast.For):
                value = self.expr(node.iter, 'ref')
                items = self.iterate(value)
                if items is None:
                    self.invalidate(node)
                    continue
                self.loop_depth += 1
                try:
                    for item in items:
                        self.assign(node.target,item)
                        self.statements(node.body)
                finally:
                    self.loop_depth -= 1
                self.statements(node.orelse)
            elif isinstance(node, ast.If):
                test = self.expr(node.test, 'ref')
                if test.constant is not None:
                    self.statements(node.body if test.constant else node.orelse)
                else:
                    self.uncertain('dynamic branch')
                    self.invalidate(node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 're': self.regex_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module == 're':
                    for alias in node.names:
                        if alias.asname and alias.asname != alias.name:
                            self.uncertain('aliased regex function')
                        else: self.regex_functions.add(alias.name)
            elif isinstance(node, (ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                if isinstance(node,ast.ClassDef) or node.decorator_list or node.args.defaults or any(node.args.kw_defaults):
                    self.uncertain('definition with potentially executable defaults/decorators/bases')
                self.assign(ast.Name(id=node.name), Value(kind='callable'))
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    if isinstance(target,ast.Name): self.env.pop(target.id,None)
            elif isinstance(node, ast.Pass):
                pass
            elif isinstance(node, (ast.Raise, ast.Return, ast.Break, ast.Continue)):
                self.uncertain(f'control transfer: {type(node).__name__}')
                return
            else:
                self.uncertain(f'unsupported statement: {type(node).__name__}')
                self.invalidate(node)

    def invalidate(self, node):
        for child in ast.walk(node):
            if isinstance(child,ast.Name) and isinstance(child.ctx,ast.Store):
                self.env[child.id] = Value()

    def block_facts(self, code, turn):
        self.turn = turn
        self.block = dict(turn=turn, block_index=len(self.blocks), code=code, parse_ok=True,
                          accesses=[], reads=[], searches=[], subcalls=[], assigned=[], reused=[], literals=[], uncertainties=[])
        self.blocks.append(self.block)
        if len(code) > self.MAX_SOURCE_CHARS:
            self.block['parse_ok'] = None
            self.uncertain('source character limit')
            return
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, RecursionError):
            self.block['parse_ok'] = False
            return
        nodes = list(ast.walk(tree))
        self.block['literals'] = [str(n.value) for n in nodes if isinstance(n,ast.Constant) and isinstance(n.value,(str,int,float))]
        if len(nodes) > self.MAX_NODES:
            self.uncertain('AST node limit')
            return
        try:
            self.statements(tree.body)
        except (RecursionError, OverflowError):
            self.uncertain('AST analysis resource limit')
