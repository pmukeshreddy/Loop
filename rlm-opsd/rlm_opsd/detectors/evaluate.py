"""D1–D19 evaluation over logged evidence and bounded AST facts."""
import ast
import re
import sys
from collections.abc import Mapping

from rlm_opsd.harness.protocol import parse_turn
from .config import DetectorConfig
from .facts import Extractor, Value


def all_known(values):
    values = list(values)
    return False if False in values else None if None in values else True


def coverage(events, total, uncertain):
    if total is None:
        return None, None
    intervals = []
    unknown = uncertain
    for event in events:
        if event['kind'] not in ('read','search','scan','subcall') or not event['context']:
            continue
        if event['ranges'] is None:
            unknown = True
        else:
            intervals.extend(event['ranges'])
    end = covered = 0
    for lo, hi in sorted(intervals):
        lo, hi = max(0,lo), min(total,hi)
        covered += max(0,hi-max(lo,end))
        end = max(end,hi)
    lower = covered/total if total else 0.0
    return (None if unknown and lower < 1 else lower), lower


def finishes(turns):
    found, malformed = [], False
    for turn in turns:
        rest = turn.get('assistant_text','')
        while rest:
            parsed = parse_turn(rest)
            if parsed.finish_error:
                malformed = True
            if not parsed.finish_type:
                break
            found.append((parsed.finish_type,parsed.finish_argument))
            rest = parsed.ignored_after_finish
    return found, malformed


def error_name(turn):
    text = str(turn.get('error') or '')
    if not text:
        # Look only for traceback-style lines, not any incidental mention of Error.
        output = turn.get('stdout_truncated','')
        if 'Traceback (most recent call last)' in output or re.search(r'^\w*(?:Error|Exception):',output,re.M):
            text = output
    match = re.search(r'\b([A-Za-z_]\w*(?:Error|Exception))\b',text)
    return match[1] if match else text or None


def normalized(code):
    try:
        return ast.dump(ast.parse(code), include_attributes=False)
    except (SyntaxError, ValueError, RecursionError):
        return code.strip()


def validate_trace(trace):
    if hasattr(trace,'model_dump'):
        trace = trace.model_dump()
    if not isinstance(trace,Mapping) or not isinstance(trace.get('turns'),list):
        raise ValueError('trajectory must contain a turns list')
    for key in ('task_id','family','domain'):
        if not isinstance(trace.get(key),str) or not trace[key]:
            raise ValueError(f'trajectory requires {key}')
    if not isinstance(trace.get('tags'),list) or any(not isinstance(t,str) for t in trace['tags']):
        raise ValueError('tags must be strings')
    for turn in trace['turns']:
        if not isinstance(turn,dict) or not isinstance(turn.get('assistant_text'),str):
            raise ValueError('turn must contain assistant_text')
        if not isinstance(turn.get('code_blocks',[]),list) or any(not isinstance(c,str) for c in turn.get('code_blocks',[])):
            raise ValueError('code_blocks must contain strings')
        if not isinstance(turn.get('stdout_truncated',''),str):
            raise ValueError('stdout_truncated must be text')
        if type(turn.get('stdout_raw_chars',0)) is not int or turn.get('stdout_raw_chars',0) < 0:
            raise ValueError('stdout_raw_chars must be nonnegative')
        if not isinstance(turn.get('subcalls',[]),list):
            raise ValueError('subcalls must be a list')
        for call in turn.get('subcalls',[]):
            if not isinstance(call,dict) or type(call.get('prompt_chars')) is not int or not 0 <= call['prompt_chars'] <= sys.maxsize:
                raise ValueError('subcall prompt_chars must be a nonnegative Python string length')
    if not isinstance(trace.get('final'),dict):
        raise ValueError('trajectory requires final object')
    return trace


def analyze_trajectory(trace, config: DetectorConfig, *, task_metadata=None):
    """Return JSON-safe facts, detector values, counts and a three-valued tag match.

    A null detector means missing/unsupported evidence or not applicable. Logged
    call counts are authoritative. AST ranges describe supplied input coverage,
    not how far a regex engine or model actually inspected that input.
    """
    trace = validate_trace(trace)
    if not isinstance(config,DetectorConfig):
        raise TypeError('config must be DetectorConfig')
    metadata = trace.get('context_metadata')
    if task_metadata is not None:
        external = task_metadata.get('context_metadata',task_metadata)
        external = {k: external[k] for k in ('context_type','context_total_length','context_lengths') if k in external}
        if metadata is not None and metadata != external:
            raise ValueError('external context metadata conflicts with trajectory')
        metadata = external
    if metadata is not None:
        from rlm_opsd.harness.trajectory import ContextMetadataTrace
        metadata = ContextMetadataTrace.model_validate(metadata).model_dump()
    engine = Extractor(metadata)
    turns = trace['turns']
    for index,turn in enumerate(turns):
        for code in turn.get('code_blocks',[]):
            engine.block_facts(code,index)
        if error_name(turn) and engine.block is not None:
            engine.uncertain('runtime error: execution location unavailable')
    events, searches, calls = engine.events,engine.searches,engine.calls
    unknown = engine.unknown.copy()
    uncertain = bool(unknown)
    if metadata is None:
        unknown.append('context geometry unavailable; supply context_metadata')
    detectors = {f'D{i}':None for i in range(1,20)}
    touches = [e for e in events if e['context']]
    if touches:
        first = [e for e in touches if e['block'] == touches[0]['block']]
        detectors['D1'] = all_known(True if e['kind'] in ('probe','iteration') else
            (None if e['size'] is None else e['size'] <= config.probe_max_chars)
            if e['kind'] in ('read','print') and not e['whole'] else False for e in first)
    dumps = [e for e in events if e['kind'] == 'print']
    detectors['D2'] = all_known(False if e['whole'] else None if e['size'] is None else e['size'] <= config.dump_threshold for e in dumps)
    reads = [e for e in events if e['kind'] == 'read']
    large = [e for e in reads if e['size'] is None or e['size'] > config.read_threshold]
    if 'sparse' in trace['tags']:
        detectors['D3'] = bool(searches) and (not large or searches[0]['order'] < large[0]['order'])
        if large and large[0]['size'] is None and not detectors['D3']:
            detectors['D3'] = None
    # A lone print(len(search_result), ...) associates a numeric leading output
    # with that search. Extra prints/blocks make stdout association ambiguous.
    for ti,turn in enumerate(turns):
        prints = [p for p in engine.prints if p['turn'] == ti]
        if len(prints) == 1 and len(turn.get('code_blocks',[])) == 1 and not error_name(turn):
            values = prints[0]['values']
            count_ids = values[0].count_of if values else set()
            match = re.match(r'^\s*(\d+)(?=\s|$)',turn.get('stdout_truncated',''))
            if len(count_ids) == 1 and match:
                engine.searches[next(iter(count_ids))]['hit_count'] = int(match[1])
    refinements = []
    for i,search in enumerate(searches):
        count = search['hit_count']
        if count is None:
            # A subsequent search without a prior hit count is not evidence of refinement.
            if i < len(searches)-1: refinements.append(None)
        elif count == 0 or count > config.many_hits:
            if i+1 == len(searches): refinements.append(False)
            elif search['pattern'] is None or searches[i+1]['pattern'] is None: refinements.append(None)
            else: refinements.append(searches[i+1]['pattern'] != search['pattern'])
        else:
            refinements.append(True)
    detectors['D4'] = all_known(refinements) if refinements else None
    content_reads = [e for e in reads if e['searches'] or e['size'] is None or e['size'] > config.probe_max_chars]
    detectors['D5'] = all_known(e['window'] for e in content_reads) if content_reads else None
    detectors['D6'] = any(s['chained'] for s in searches) if searches else None
    found, malformed = finishes(turns)
    final = trace['final']
    final_value = Value()
    if len(found) == 1:
        typ,arg = found[0]
        if typ == 'FINAL_VAR':
            final_value = engine.env.get(arg,Value())
        else:
            # A literal FINAL may reproduce a single printed computed value.
            for p in engine.prints:
                if len([q for q in engine.prints if q['turn'] == p['turn']]) == 1 and len(p['values']) == 1:
                    value = p['values'][0]
                    if value.computed and turns[p['turn']].get('stdout_truncated','').strip() == arg:
                        final_value = value
    detectors['D7'] = final_value.searches <= engine.verified if final_value.searches else None
    logged = [c for t in turns for c in t.get('subcalls',[])]
    sizes = [c['prompt_chars'] for c in logged]
    call_checks = []
    for ti,turn in enumerate(turns):
        sites = [c for c in calls if c['turn'] == ti]
        runtime = turn.get('subcalls',[])
        for i,site in enumerate(sites):
            site['prompt_chars'] = ([runtime[i]['prompt_chars']] if len(sites) == len(runtime) else
                                    [r['prompt_chars'] for r in runtime] if len(sites) == 1 else [])
            site['runtime_alignment'] = 'ordered' if len(sites) == len(runtime) else 'single_site' if len(sites) == 1 else 'unknown'
        if sites and not runtime:
            call_checks.append(None)
        elif runtime:
            if any(c.get('error') for c in runtime):
                call_checks.append(False)
            elif len(sites) == len(runtime):
                call_checks.extend(site['context'] and
                                   (not site['whole'] or actual['prompt_chars'] <= config.subcall_max_chars)
                                   for site,actual in zip(sites,runtime))
            elif sites and len({(s['context'],s['whole'],bool(s['searches'])) for s in sites}) == 1:
                site = sites[0]
                call_checks.append(site['context'] and
                                   (not site['whole'] or max(c['prompt_chars'] for c in runtime) <= config.subcall_max_chars))
            else:
                call_checks.append(None)
    detectors['D8'] = all_known(call_checks) if call_checks else None
    if logged:
        detectors['D9'] = any(c['in_loop'] for c in calls) if calls else None
        limit = config.max_subcalls_expected.get(trace['task_id'],config.max_subcalls_expected.get(trace['family']))
        detectors['D10'] = len(logged) <= limit and sum(sizes)/len(sizes) >= config.min_batch_chars if limit is not None else None
        if limit is None:
            unknown.append('no max_subcalls_expected for task_id or family')
        detectors['D11'] = all(c['stored'] for c in calls) if calls else None
    detectors['D12'] = any(b['reused'] for b in engine.blocks)
    detectors['D13'] = not any(len(literal) >= config.hand_copy_min_chars and literal in turns[i].get('stdout_truncated','')
                               for b in engine.blocks for literal in b['literals'] for i in range(b['turn']))
    detectors['D14'] = bool(final_value.computed) if found else None
    clean = len(found) == 1 and not malformed and final.get('type') in ('FINAL','FINAL_VAR') and not final.get('error')
    if clean:
        typ,arg = found[0]
        clean = typ == final['type'] and bool(arg) and not any(t.get('finish_error') for t in turns)
        if typ == 'FINAL_VAR':
            clean = clean and arg.isidentifier() and bool(str(final.get('value','')).strip())
        else:
            clean = clean and arg == final.get('value')
        plan = r'''^\s*["']?(?:(?:next|first)[,:]?\s+)?(?:I\s+(?:will|need to|should|plan to|am going to)|we\s+(?:will|should|need to|are going to))\b'''
        steps = r'^\s*["\']?(?:first|next)[,:]?\s+(?:search|read|inspect|scan|chunk|aggregate|calculate)\b'
        clean = clean and not (re.match(plan,str(final.get('value','')),re.I) or re.match(steps,str(final.get('value','')),re.I))
    detectors['D15'] = bool(clean)
    syntax_blocks = sum(b['parse_ok'] is False for b in engine.blocks)
    ambiguous_syntax = any(b['parse_ok'] is None for b in engine.blocks)
    for ti,turn in enumerate(turns):
        blocks = [b for b in engine.blocks if b['turn'] == ti]
        if error_name(turn) in ('SyntaxError','IndentationError','TabError') and not any(not b['parse_ok'] for b in blocks):
            if len(blocks) == 1: syntax_blocks += 1
            elif blocks: ambiguous_syntax = True
    detectors['D16'] = None if ambiguous_syntax or not engine.blocks else syntax_blocks/len(engine.blocks)
    errors, recoveries = [], []
    for i,b in enumerate(engine.blocks):
        error = 'SyntaxError' if b['parse_ok'] is False else error_name(turns[b['turn']])
        if not error: continue
        errors.append(error)
        # Aggregated runtime errors cannot be attributed within a multi-block turn.
        same_turn = [q for q in engine.blocks if q['turn'] == b['turn']]
        if len(same_turn) > 1 and b['parse_ok']:
            recoveries.append(None)
            continue
        next_block = engine.blocks[i+1] if i+1 < len(engine.blocks) else None
        recoveries.append(bool(next_block) and normalized(next_block['code']) != normalized(b['code']) and
                          ('SyntaxError' if not next_block['parse_ok'] else error_name(turns[next_block['turn']])) != error)
    detectors['D17'] = all_known(recoveries) if recoveries else None
    reliable_events = [e for e in events if not error_name(turns[e['turn']])]
    detectors['D18'],lower = coverage(reliable_events,engine.total,uncertain)
    if detectors['D18'] is None and metadata is not None:
        unknown.append('unresolved content ranges or control flow; coverage is a lower bound')
    strategy = 'other'
    for b in engine.blocks:
        relevant = [e for e in events if e['block'] == b['block_index'] and e['context'] and e['kind'] not in ('probe','iteration')]
        if not relevant: continue
        significant = [e for e in relevant if e['kind'] in ('search','subcall') or e['whole'] or e['size'] is None or e['size'] > config.probe_max_chars]
        if not significant: continue
        first = significant[0]
        if first['kind'] == 'search': strategy = 'regex_filter'
        elif first['kind'] == 'subcall': strategy = 'whole_subcall' if first['whole'] else 'chunk_subcall'
        elif b['subcalls'] and not any(e['kind'] == 'print' and e['order'] < b['subcalls'][0]['order'] for e in relevant):
            strategy = 'whole_subcall' if b['subcalls'][0]['whole'] else 'chunk_subcall'
        else: strategy = 'direct_read'
        break
    detectors['D19'] = strategy
    if uncertain:
        # Preserve proven violations; never turn unsupported behavior into a pass.
        for key in ('D1','D2','D3','D4','D5','D6','D7','D8','D9','D11','D12','D14'):
            if detectors[key] is True: detectors[key] = None
        detectors['D19'] = None
    required = ['D15']
    tags = set(trace['tags'])
    if 'large_context' in tags: required += ['D1','D2']
    if 'sparse' in tags: required += ['D3','D5','D7']
    if 'chained_search' in tags: required += ['D6']
    if tags & {'dense','needs_subcalls'}: required += ['D8','D9','D10','D11']
    if 'aggregate_in_code' in tags: required += ['D14']
    if errors: required += ['D17']
    requirements = [detectors[k] for k in required]
    if tags & {'dense','needs_subcalls'}:
        requirements.append(None if detectors['D18'] is None else detectors['D18'] > config.dense_coverage_min)
    if 'output_in_variable' in tags: requirements.append(final.get('type') == 'FINAL_VAR')
    # An oversized whole-context call is disallowed even on a small-context task.
    forbidden = any(c['whole'] and any(actual['prompt_chars'] > config.subcall_max_chars for actual in turns[c['turn']].get('subcalls',[])) for c in calls)
    unresolved_oversized = any(actual['prompt_chars'] > config.subcall_max_chars for actual in logged) and (uncertain or any(c is None for c in call_checks))
    requirements.append(False if forbidden else None if unresolved_oversized else True)
    counts = dict(subcall_count=len(logged),subcall_mean_prompt_chars=sum(sizes)/len(sizes) if sizes else 0.0,
                  subcall_max_prompt_chars=max(sizes,default=0),
                  truncation_events=sum(bool(re.search(r'\[truncated: full output length \d+ chars\]',t.get('stdout_truncated',''))) for t in turns),
                  syntax_error_blocks=None if ambiguous_syntax else syntax_blocks,code_blocks=len(engine.blocks))
    return dict(task_id=trace['task_id'],family=trace['family'],domain=trace['domain'],tags=list(trace['tags']),
                size_bucket=trace.get('size_bucket', (task_metadata or {}).get('size_bucket')),
                detectors=detectors,task_tag_match=all_known(requirements),counts=counts,
                coverage_lower_bound=lower,unknown_reasons=unknown,facts=engine.blocks)
