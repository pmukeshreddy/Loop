"""Resumable AgentInstruct-style generation: analyze → generate → materialize →
solve → verify → check practice → review → vary.

Every stage writes its output atomically under `work_dir/candidates/<cid>/`; a
restarted run skips completed stages. Rejections are terminal and appended to
`work_dir/rejections.jsonl` with a reason code and detail.
"""
import asyncio
from collections import Counter
from pathlib import Path
import re
import shutil
import time
import traceback

import yaml

from rlm_opsd.harness.config import HarnessConfig

from .analysis import facts_digest, repository_facts
from .decontam import HeldoutIndex, query_overlap
from .llm import ResponsesLLM
from .materialize import Rejected, materialize
from .models import BEHAVIORS, SETTINGS, CandidateSpec, canonical, digest, normalized
from .practice import check_behaviors
from .repos import RepoSpec, Workspace, inventory
from .roles import Roles, files_block, load_skills
from .solver import solve
from .store import Store, read_json, write_json
from .verify import normalize, matches, parse_answer, run_oracle, set_scores, verify_patch

BEHAVIOR_MIX = dict(inspect_locate=0.2, chunked_subcalls=0.18, recursive_decomposition=0.17,
                    persistent_state=0.15, combine_verify_finish=0.15, direct_solve=0.15)
TEST_AUTHORING = re.compile(r'\b(?:add|adding|include|including|write|writing|create|creating|containing|plus)\b'
                            r'[^.;]{0,60}?\b(?:regression|acceptance|unit)?[- ]?tests?(?: files?| cases?)?\b(?! (?:would|that|which|fail|pass))',
                            re.I)
RLM_TERMS = re.compile(r'llm_query|rlm_query|FINAL_VAR|FINAL\s*\(|\bREPL\b|\bsub-?calls?\b|\bsub-?LLM|'
                       r'recursive (?:call|sub)|language model|context\[|\bthe context variable', re.I)


def grams(text, n):
    words = normalized(text).split()
    width = min(n, len(words))
    return {tuple(words[i:i + width]) for i in range(len(words) - width + 1)} if width else set()


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


class Pipeline:
    def __init__(self, config, *, config_dir='.', repos=None, max_rounds=None, targets=None, focus=None, log=print):
        self.config, self.log = config, log
        # Focused top-up: seeds may only aim at these primary behaviors, and targets count them.
        unknown = set(focus or ()) - set(BEHAVIORS)
        if unknown:
            raise ValueError(f'unknown focus behaviors: {sorted(unknown)}')
        self.focus = set(focus) if focus else None
        root = Path(config_dir)
        self.work = (root / config['work_dir']).resolve()
        self.sources = (root / config['sources_dir']).resolve()
        self.store = Store(self.work)
        self.splits = read_json(self.work / 'splits.json')
        lock = read_json(self.work / 'sources.lock.json')
        if not self.splits or not lock:
            raise ValueError('run `python -m rlm_opsd.tasks prepare` first (splits and sources lock missing)')
        specs = [RepoSpec.from_config(r) for r in config['repositories']]
        if repos:
            specs = [s for s in specs if s.name in repos or s.slug in repos]
        self.repos = specs
        self.workspaces = {s.name: Workspace(s, self.sources, config['python']) for s in specs}
        self.max_rounds = max_rounds or config['generation']['max_rounds_per_repo']
        self.targets = targets or config['targets']
        self.harness = HarnessConfig.from_yaml(root / config['harness_config'])
        overrides = config.get('solver_harness_overrides') or {}
        if set(overrides) - {'subcall_timeout_s', 'sandbox'} or set(overrides.get('sandbox', {})) - {'wall_time_s'}:
            raise ValueError('solver_harness_overrides may only relax timing limits')
        base = self.harness.model_dump()
        self.solver_harness = HarnessConfig.model_validate(
            {**base, **{k: v for k, v in overrides.items() if k != 'sandbox'},
             'sandbox': {**base['sandbox'], **overrides.get('sandbox', {})}})
        models = config['models']
        self.llm = ResponsesLLM(model=models['model'], auth=models['auth'], timeout_s=models['request_timeout_s'],
                                usage_log=self.work / 'usage.jsonl')
        self.skills = load_skills()
        self.roles = Roles(self.llm, self.skills, models['effort'])
        self.candidate_slots = asyncio.Semaphore(config['generation']['concurrency'])
        self.test_lock = asyncio.Semaphore(config['generation']['test_concurrency'])
        self.repo_locks = {s.name: asyncio.Lock() for s in specs}
        index_path = root / config['heldout']['index']
        self.heldout = HeldoutIndex.load(index_path) if index_path.exists() else HeldoutIndex()
        write_json(self.work / 'run.json', dict(
            config=config, skills={k: v['sha256'] for k, v in self.skills.items()},
            harness=self.harness.model_dump(), solver_harness=self.solver_harness.model_dump(), started=time.time()))

    # ---------- bookkeeping ----------
    def repo_target(self, repo):
        split = self.splits['assignment'][repo.name]
        members = sorted(n for n, s in self.splits['assignment'].items() if s == split)
        base, extra = divmod(self.targets[split], len(members))
        return base + (1 if members.index(repo.name) < extra else 0)

    def candidates(self, repo_name=None, status=None):
        rows = []
        for cid in self.store.ids():
            meta = self.store.read(cid, 'meta.json')
            if repo_name and meta['repo'] != repo_name:
                continue
            if status and self.store.status(cid) != status:
                continue
            rows.append((cid, meta))
        return rows

    def progress(self, repo):
        """Accepted tasks counted toward the repository target (focus families only in focus mode)."""
        rows = self.candidates(repo.name, 'accepted')
        if not self.focus:
            return len(rows)
        return sum(self.store.read(cid, 'accepted.json')['family'] in self.focus for cid, _ in rows)

    def baseline(self, repo):
        return read_json(self.work / 'repos' / repo.slug / 'baseline.json')

    # ---------- top level ----------
    async def run(self):
        await asyncio.gather(*(self.repo_loop(repo) for repo in self.repos))
        return self.summary()

    def summary(self):
        counts = Counter()
        for cid, meta in self.candidates():
            counts[(meta['split'], self.store.status(cid))] += 1
        return {f'{split}:{status}': n for (split, status), n in sorted(counts.items())}

    async def repo_loop(self, repo):
        try:
            dossier = await self.dossier(repo)
        except Exception as exc:  # noqa: BLE001 - recorded, repository skipped
            self.store.log('events.jsonl', dict(repo=repo.name, event='analysis_failed', error=repr(exc)[:500]))
            self.log(f'[{repo.name}] analysis failed: {exc!r}')
            return
        target = self.repo_target(repo)
        await self.process_many([cid for cid, _ in self.candidates(repo.name, 'pending')])
        await self.vary_accepted(repo, target)
        for round_index in range(1, self.max_rounds + 1):
            accepted = self.progress(repo)
            # dev_behavior must represent every family (teacher-gate preflight); keep
            # generating within the round cap while one is missing from the split.
            if accepted >= target and not self.missing_families(self.splits['assignment'][repo.name]):
                break
            new = await self.generate_round(repo, dossier, round_index)
            await self.process_many(new)
            await self.vary_accepted(repo, target)
        self.log(f'[{repo.name}] done: {self.progress(repo)}/{target} accepted'
                 + (f' in focus {sorted(self.focus)}' if self.focus else ''))

    async def process_many(self, cids):
        await asyncio.gather(*(self.process(cid) for cid in cids))

    # ---------- analysis ----------
    def documents(self, repo):
        ctx = self.config['context']
        return inventory(repo, self.workspaces[repo.name].tree, exclude=ctx['exclude'],
                         max_file_chars=ctx['max_file_chars'])

    async def dossier(self, repo):
        path = self.work / 'repos' / repo.slug / 'dossier.json'
        if path.exists():
            return read_json(path)
        documents = self.documents(repo)
        facts = repository_facts(repo, documents)
        write_json(self.work / 'repos' / repo.slug / 'facts.json', facts)
        by_path = {d.path: d for d in documents}
        ranked = sorted(facts['source_modules'], key=lambda r: (-len(r['imported_by']) - len(r['imports']), r['path']))
        source_text = files_block([(r['path'], by_path[r['path']].text) for r in ranked],
                                  self.config['generation']['analysis_source_chars'])
        baseline = self.baseline(repo)
        summary = (f"{len(baseline['stable_passing'])} tests pass on every baseline run; "
                   f"{len(baseline['failing'])} fail or error at the pinned commit; "
                   f"{len(baseline['flaky'])} change outcome between runs.")
        dossier = await self.roles.analyze(repo=repo, facts_digest=facts_digest(facts), source_text=source_text,
                                           baseline_summary=summary)
        known = set(by_path)
        for section in ('mechanisms', 'defect_sites', 'semantic_sets', 'focused_units'):
            for item in dossier.get(section, []) or []:
                files = item.get('files') or ([item['file']] if item.get('file') else [])
                item['_unknown_files'] = [f for f in files if f not in known]
        write_json(path, dossier)
        self.log(f'[{repo.name}] dossier: {len(dossier.get("mechanisms", []))} mechanisms, '
                 f'{len(dossier.get("defect_sites", []))} defect sites')
        return dossier

    # ---------- generation ----------
    def focus_files(self, repo, dossier, round_index):
        """Rotate through dossier entries so each round is grounded in different code."""
        documents = {d.path: d for d in self.documents(repo)}
        pools = []
        for section in ('mechanisms', 'defect_sites', 'semantic_sets', 'focused_units'):
            items = [i for i in dossier.get(section, []) or [] if isinstance(i, dict)]
            if items:
                pools.append(items[(round_index - 1) % len(items)])
                if len(items) > 1:
                    pools.append(items[(round_index * 2) % len(items)])
        files = []
        for item in pools:
            for path in (item.get('files') or []) + ([item['file']] if item.get('file') else []) + \
                    (item.get('tests') or []) + (item.get('surfaces_in') or []):
                if path in documents and path not in files:
                    files.append(path)
        return [(p, documents[p].text) for p in files], pools

    def missing_families(self, split):
        if split != 'dev_behavior':
            return []
        present = {self.store.read(cid, 'accepted.json')['family'] for cid, meta in self.candidates(status='accepted')
                   if meta['split'] == split}
        return [b for b in BEHAVIORS if b not in present]

    def quotas(self, repo):
        if self.focus:
            needed = ', '.join(sorted(self.focus))
            return (f'This round is a focused top-up. Every task must have one of these as its primary behavior: '
                    f'{needed}. Choose investigations whose properties genuinely make that behavior useful '
                    f'(much more selected text to understand than fits small reads; independent sub-investigations '
                    f'whose findings are combined in code). Accepted so far in focus for this repository: '
                    f'{self.progress(repo)} of {self.repo_target(repo)}.')
        accepted = Counter(self.store.read(cid, 'accepted.json')['family']
                           for cid, _ in self.candidates(repo.name, 'accepted'))
        target = self.repo_target(repo)
        lines, needs = [], []
        for behavior in BEHAVIORS:
            want = max(1, round(BEHAVIOR_MIX[behavior] * target))
            lines.append(f'- {behavior}: {accepted[behavior]} accepted (aim for about {want})')
            if accepted[behavior] < want:
                needs.append(behavior)
        lines.append('Most needed as primary behaviors: ' + (', '.join(needs) or 'any'))
        missing = self.missing_families(self.splits['assignment'][repo.name])
        if missing:
            lines.append('Families not yet represented anywhere in this evaluation split (highest priority, '
                         'only where the repository genuinely supports them): ' + ', '.join(missing))
        kinds = Counter(self.store.read(cid, 'spec.json')['answer_kind'] for cid, _ in self.candidates(repo.name)
                        if self.store.read(cid, 'spec.json'))
        lines.append('Answer kinds generated so far for this repository: '
                     + (', '.join(f'{k} {v}' for k, v in sorted(kinds.items())) or 'none'))
        return '\n'.join(lines)

    def settings(self, dossier):
        extra = [s['setting'] for s in dossier.get('proposed_settings', []) or []
                 if isinstance(s, dict) and re.fullmatch(r'[a-z][a-z0-9_]{2,48}', str(s.get('setting', '')))]
        return list(SETTINGS) + [s for s in extra if s not in SETTINGS]

    async def generate_round(self, repo, dossier, round_index):
        marker = self.work / 'repos' / repo.slug / f'round-{round_index:02d}.json'
        if marker.exists():
            return [cid for cid in read_json(marker)['candidates'] if self.store.status(cid) == 'pending']
        files, focus = self.focus_files(repo, dossier, round_index)
        avoid = [self.store.read(cid, 'spec.json')['question'][:220] for cid, _ in self.candidates(repo.name)
                 if self.store.read(cid, 'spec.json')]
        count = self.config['generation']['seeds_per_round']
        async with self.candidate_slots:
            try:
                specs, invalid = await self.roles.generate(
                    repo=repo, dossier={k: v for k, v in dossier.items() if not k.startswith('_')},
                    files_text=files_block(files, self.config['generation']['generator_file_chars']),
                    count=count, quotas=self.quotas(repo), avoid=avoid[-60:], settings=self.settings(dossier))
            except Exception as exc:  # noqa: BLE001
                self.store.log('events.jsonl', dict(repo=repo.name, event='generation_failed', round=round_index,
                                                    error=repr(exc)[:500]))
                write_json(marker, dict(candidates=[], error=repr(exc)[:500]))
                return []
        split = self.splits['assignment'][repo.name]
        cids = []
        for index, spec in enumerate(specs):
            cid = f'{repo.slug}-r{round_index:02d}-{index:02d}'
            self.store.write(cid, 'meta.json', dict(cid=cid, repo=repo.name, split=split, origin='seed', round=round_index,
                                                    parent_id=None, focus=[f.get('id') for f in focus]))
            self.store.write(cid, 'spec.json', spec.model_dump())
            cids.append(cid)
        for item in invalid:
            cid = f'{repo.slug}-r{round_index:02d}-x{item["index"]:02d}'
            self.store.write(cid, 'meta.json', dict(cid=cid, repo=repo.name, split=split, origin='seed',
                                                    round=round_index, parent_id=None))
            self.store.write(cid, 'invalid.json', item)
            self.store.reject(cid, 'generate', 'invalid_spec', item['error'])
        write_json(marker, dict(candidates=cids, invalid=len(invalid), focus=[f.get('id') for f in focus]))
        self.log(f'[{repo.name}] round {round_index}: {len(specs)} specs, {len(invalid)} invalid')
        return cids

    # ---------- per-candidate stage machine ----------
    async def process(self, cid):
        if self.store.status(cid) != 'pending' or self.store.read(cid, 'spec.json') is None:
            return  # terminal, or a variation whose editor has not produced a spec yet
        async with self.candidate_slots:
            stage = 'start'
            try:
                meta = self.store.read(cid, 'meta.json')
                repo = next(r for r in self.repos if r.name == meta['repo'])
                workspace = self.workspaces[repo.name]
                spec = CandidateSpec.model_validate(self.store.read(cid, 'spec.json'))
                stage = 'screen'
                self.screen(spec)
                stage = 'materialize'
                record = self.store.read(cid, 'materialized.json')
                if record is None:
                    out = self.store.path(cid, 'logs')
                    out.mkdir(parents=True, exist_ok=True)
                    record, context = await materialize(spec, workspace, self.baseline(repo), self.config,
                                                        self.test_lock, out)
                    self.store.write(cid, 'context.json', context)
                    self.store.write(cid, 'materialized.json', record)
                context = self.store.read(cid, 'context.json')
                stage = 'oracle'
                truth = await self.ground_truth(cid, spec, record, repo, workspace)
                stage = 'baseline'  # cheap, so it runs before the reference solve
                await self.no_repository_check(cid, spec, repo, truth)
                stage = 'solve'
                verification = self.store.read(cid, 'verification.json')
                attempts = self.config['generation'].get('solver_attempts', 2)
                stored = sorted(self.store.path(cid, '').glob('solve-*.json'),
                                key=lambda p: int(p.stem.split('-')[1]))
                attempt = len(stored)
                if verification is None and stored:
                    # Re-verify stored solves (resume, or after a verifier fix) before solving again.
                    stage = 'verify'
                    for path in stored:
                        verification = await self.verify(cid, spec, record, truth, read_json(path), workspace)
                        self.store.write(cid, 'verification.json', verification)
                        if verification['passed']:
                            break
                    stage = 'solve'
                while verification is None or not verification['passed']:
                    if attempt >= attempts:
                        raise Rejected('reference_answer_incorrect', verification['detail'] if verification else '')
                    attempt += 1
                    result = await self.solve(cid, spec, context, record, attempt)
                    stage = 'verify'
                    verification = await self.verify(cid, spec, record, truth, result, workspace)
                    self.store.write(cid, 'verification.json', verification)
                    stage = 'solve'
                stage = 'practice'
                practice = await self.practice(cid, spec, record, verification)
                stage = 'review'
                await self.review_and_accept(cid, spec, record, truth, verification, practice, repo, meta)
            except Rejected as exc:
                self.store.reject(cid, stage, exc.code, exc.detail)
            except Exception as exc:  # noqa: BLE001 - infrastructure errors are recorded, not hidden
                self.store.write(cid, 'error.json', dict(stage=stage, error=repr(exc)[:2000],
                                                         traceback=traceback.format_exc()[-6000:]))
                self.store.reject(cid, stage, 'pipeline_error', repr(exc)[:1000])

    def screen(self, spec):
        filters = self.config['filters']
        if getattr(self, 'focus', None) and spec.primary_behavior not in self.focus:
            raise Rejected('off_focus', spec.primary_behavior)
        if len(spec.question) > filters['max_question_chars']:
            raise Rejected('question_too_long', f'{len(spec.question)} chars')
        match = RLM_TERMS.search(spec.question)
        if match:
            raise Rejected('prescribes_rlm_operations', match[0])
        authoring = TEST_AUTHORING.search(spec.question)
        if authoring and not re.search(r'\b(?:existing|currently passing|newly fail)', authoring[0], re.I):
            raise Rejected('requests_test_authoring', authoring[0])
        longest = max((len(block.strip('\n').splitlines()) for block in
                       re.findall(r'```[^\n]*\n(.*?)```', spec.question, re.S)), default=0)
        if longest > filters['max_question_code_lines']:
            raise Rejected('embedded_program_quiz', f'{longest}-line code listing in the question')

    async def ground_truth(self, cid, spec, record, repo, workspace):
        cached = self.store.read(cid, 'truth.json')
        if cached is not None:
            return cached
        if spec.answer_kind == 'patch':
            truth = dict(kind='tests', fail_to_pass=record['fail_to_pass'], hidden_tests=record['hidden_tests'])
        elif spec.answer_kind == 'test_ids':
            truth = dict(kind='impact', answer=record['impact_tests'])
        elif spec.answer_kind == 'symbols' and spec.setup_patch:
            symbols = record['ground_truth_symbols']
            if any(s.endswith(('::<module>', '::<file>')) for s in symbols):
                raise Rejected('defect_outside_function', f'{symbols}')
            truth = dict(kind='defect_symbols', answer=symbols)
        else:
            documents = {d.path: d.text for d in self.documents(repo)}
            paths = [e.path for e in spec.evidence] + (spec.context.files if spec.context.scope == 'files' else [])
            relevant = [(p, documents[p]) for p in dict.fromkeys(paths) if p in documents]
            script = await self.roles.oracle(repo=repo, question=spec.question, answer_kind=spec.answer_kind,
                                             answer_format=spec.answer_format,
                                             files_text=files_block(relevant, 120000),
                                             file_list='\n'.join(record['documents'][:600]))
            self.store.path(cid, 'oracle.py').write_text(script, encoding='utf-8')
            value, output = await run_oracle(script, spec, workspace, self.config)
            try:
                normalized_value = normalize(value, spec.answer_kind, spec.answer_format)
            except (TypeError, ValueError, AttributeError) as exc:
                raise Rejected('oracle_answer_wrong_format', repr(value)[:300]) from exc
            if spec.answer_format in ('set', 'ordered_list') and not value:
                raise Rejected('oracle_answer_empty')
            truth = dict(kind='oracle', answer=value, normalized=normalized_value, output_tail=output)
        self.leak_check(spec, truth)
        self.store.write(cid, 'truth.json', truth)
        return truth

    def leak_check(self, spec, truth):
        question = spec.question
        if truth['kind'] == 'defect_symbols':
            for symbol in truth['answer']:
                name = symbol.split('::')[-1].split('.')[-1]
                if len(name) >= 4 and re.search(rf'\b{re.escape(name)}\b', question):
                    raise Rejected('answer_leak', f'question names the defective symbol {name}')
        elif truth['kind'] == 'impact':
            for nodeid in truth['answer']:
                name = nodeid.split('::')[-1]
                if re.search(rf'\b{re.escape(name)}\b', question):
                    raise Rejected('answer_leak', f'question names impacted test {name}')
        elif truth['kind'] == 'oracle' and spec.answer_format == 'scalar':
            text = str(truth['answer']).strip()
            if len(text) >= 4 and text in question:
                raise Rejected('answer_leak', 'question contains the scalar answer')

    async def solve(self, cid, spec, context, record, attempt):
        logs = self.store.path(cid, f'trajectories-{attempt}')
        result = await solve(task_id=cid, family=spec.primary_behavior, tags=[], query=spec.question,
                             context=context, llm=self.llm, root_effort=self.config['models']['effort']['solver_root'],
                             subcall_effort=self.config['models']['effort']['solver_subcall'],
                             harness_config=self.solver_harness, solver_skill=self.skills['solver']['text'], log_dir=logs)
        shutil.copy(result['trajectory_path'], self.store.path(cid, f'trajectory-{attempt}.json'))
        result['attempt'] = attempt
        self.store.write(cid, f'solve-{attempt}.json', result)
        return result

    async def verify(self, cid, spec, record, truth, result, workspace):
        base = dict(attempt=result['attempt'], passed=False)
        if result['final_type'] == 'none' or result['final_error']:
            return dict(base, detail=f"no valid finish: {result['final_error']}")
        try:
            answer = parse_answer(result['final_value'], spec.answer_format)
        except ValueError as exc:
            return dict(base, detail=f'unparseable answer: {exc}')
        if spec.answer_kind == 'patch':
            try:
                evidence = await verify_patch(spec, record, answer, workspace, self.config, self.test_lock,
                                              self.store.path(cid, 'logs'))
            except Rejected as exc:
                return dict(base, detail=f'{exc.code}: {exc.detail}')
            self.store.path(cid, 'reference.patch').write_text(answer if answer.endswith('\n') else answer + '\n',
                                                               encoding='utf-8')
            return dict(base, passed=True, answer=answer, evidence=evidence, method='tests')
        try:
            predicted = normalize(answer, spec.answer_kind, spec.answer_format)
        except (TypeError, ValueError, AttributeError) as exc:
            return dict(base, detail=f'answer has the wrong shape: {exc}')
        expected = truth.get('normalized') if truth['kind'] == 'oracle' else normalize(
            truth['answer'], spec.answer_kind, spec.answer_format)
        evidence = dict(predicted=predicted, expected=expected)
        if isinstance(predicted, list) and spec.answer_format == 'set':
            evidence['precision'], evidence['recall'] = set_scores(predicted, expected)
        if not matches(predicted, expected):
            return dict(base, detail=f'mismatch: predicted {str(predicted)[:400]} expected {str(expected)[:400]}',
                        evidence=evidence)
        return dict(base, passed=True, answer=answer, evidence=evidence, method=truth['kind'])

    async def no_repository_check(self, cid, spec, repo, truth):
        if spec.answer_kind == 'patch':
            return
        cached = self.store.read(cid, 'baseline.json')
        if cached is None:
            text = await self.roles.baseline(repo=repo, question=spec.question)
            correct = False
            try:
                value = normalize(parse_answer(text, spec.answer_format), spec.answer_kind, spec.answer_format)
                expected = truth.get('normalized') if truth['kind'] == 'oracle' else normalize(
                    truth['answer'], spec.answer_kind, spec.answer_format)
                correct = matches(value, expected)
            except (ValueError, TypeError, AttributeError):
                pass
            cached = dict(answer=text[:2000], correct=correct)
            self.store.write(cid, 'baseline.json', cached)
        if cached['correct']:
            raise Rejected('answerable_without_repository', cached['answer'][:300])

    async def practice(self, cid, spec, record, verification):
        trace = read_json(self.store.path(cid, f'trajectory-{verification["attempt"]}.json'))
        result = check_behaviors(trace, spec.rlm_behaviors, context_chars=record['context_chars'],
                                 practice=self.config['practice'], harness=self.harness,
                                 direct_read_max_chars=self.config['context']['direct_read_max_chars'])
        self.store.write(cid, 'practice.json', result)
        if result['facts']['repository_execution']:
            raise Rejected('reference_executed_repository', ', '.join(result['facts']['repository_execution']))
        if not result['established']:
            evidence = result['results'][spec.primary_behavior]['evidence']
            raise Rejected('practice_mismatch', f'no intended behavior exhibited; primary: {evidence}')
        # Labels stay truthful: an unexhibited primary yields to the first exhibited intended behavior.
        result['family'] = spec.primary_behavior if spec.primary_behavior in result['established'] \
            else result['established'][0]
        result['relabeled_from'] = None if result['family'] == spec.primary_behavior else spec.primary_behavior
        self.store.write(cid, 'practice.json', result)
        return result

    def answer_key(self, spec, verification, record):
        if spec.answer_kind == 'patch':
            return canonical(dict(f2p=record['fail_to_pass'], hidden=record['hidden_tests'],
                                  setup=digest(normalized(spec.setup_patch or ''))))
        return canonical(verification['evidence']['expected'])

    async def review_and_accept(self, cid, spec, record, truth, verification, practice, repo, meta):
        parent = None
        if meta.get('parent_id'):
            parent = dict(spec=self.store.read(meta['parent_id'], 'spec.json'),
                          accepted=self.store.read(meta['parent_id'], 'accepted.json'))
        key = self.answer_key(spec, verification, record)
        if parent and parent['accepted'] and parent['accepted']['answer_key'] == key:
            raise Rejected('cosmetic_variation', 'verified answer identical to the parent task')
        overlap = query_overlap(spec.question, self.heldout, **self.config['heldout']['decontamination'])
        if overlap:
            raise Rejected('heldout_overlap', overlap)
        review = self.store.read(cid, 'review.json')
        if review is None:
            payload = dict(
                repository=repo.name, setting=spec.setting, question=spec.question,
                intended_behaviors=spec.rlm_behaviors, behaviors_established=practice['established'],
                behavior_rationale={k: v for k, v in spec.behavior_rationale.items() if k in practice['established']},
                practice_evidence={k: v['evidence'] for k, v in practice['results'].items()},
                execution_facts=practice['facts'], context=dict(scope=spec.context.scope, chars=record['context_chars'],
                                                                documents=len(record['documents']), logs=record['logs']),
                answer_kind=spec.answer_kind, answer_format=spec.answer_format,
                verified_answer=str(verification['answer'])[:3000], ground_truth=dict(
                    method=verification['method'], fail_to_pass=record['fail_to_pass'][:20],
                    impact_tests=record['impact_tests'][:30], symbols=record['ground_truth_symbols'][:10]),
                defect_or_change=(spec.setup_patch or spec.probe_patch or spec.hidden_tests_patch or '')[:3000],
                variation_of=dict(question=parent['spec']['question'],
                                  answer=str(parent['accepted']['answer'])[:1500]) if parent else None,
                accepted_in_repository=[self.store.read(other, 'accepted.json')['query'][:400]
                                        for other, _ in self.candidates(repo.name, 'accepted')][-40:])
            review = await self.roles.review(payload)
            self.store.write(cid, 'review.json', review)
        if review['verdict'] != 'accept':
            raise Rejected('review_' + '+'.join(review.get('reasons') or ['unspecified']), review.get('notes', ''))
        async with self.repo_locks[repo.name]:
            question_grams = grams(spec.question, self.config['filters']['question_ngram_size'])
            for other, _ in self.candidates(repo.name, 'accepted'):
                accepted = self.store.read(other, 'accepted.json')
                similarity = jaccard(question_grams, grams(accepted['query'], self.config['filters']['question_ngram_size']))
                if similarity > self.config['filters']['max_question_similarity']:
                    raise Rejected('near_duplicate_question', f'{other}: jaccard {similarity:.2f}')
                if accepted['answer_key'] == key:
                    raise Rejected('repeated_answer', f'same verified answer as {other}')
            established = practice['established']
            accepted = dict(
                task_id=cid, split=meta['split'], family=practice['family'], rlm_behaviors=established,
                behavior_rationale={k: spec.behavior_rationale[k] for k in established},
                intended_behaviors=spec.rlm_behaviors, setting=spec.setting, query=spec.question,
                answer=verification['answer'], answer_type=spec.answer_kind, answer_format=spec.answer_format,
                answer_key=key, size_bucket=record['size_bucket'], context_chars=record['context_chars'],
                tags=practice['tags'], parent_id=meta.get('parent_id'),
                variation=self.store.read(cid, 'suggestion.json'), origin=meta['origin'],
                repo=dict(name=repo.name, url=repo.url, ref=repo.ref, commit=repo.commit, license=repo.license),
                verification=dict(method=verification['method'], attempt=verification['attempt'],
                                  fail_to_pass=record['fail_to_pass'], hidden_tests=record['hidden_tests'],
                                  pass_to_pass_count=len(record['pass_to_pass']), impact_tests=record['impact_tests'],
                                  ground_truth_symbols=record['ground_truth_symbols'],
                                  evidence=verification.get('evidence'), stability_runs=self.config['generation']['stability_runs']),
                practice=dict(results=practice['results'], facts=practice['facts'],
                              coverage_lower_bound=practice['coverage_lower_bound'],
                              relabeled_from=practice['relabeled_from']),
                review=dict(notes=review.get('notes', ''), behavior_notes=review.get('behavior_notes', {})),
                documents=record['documents'], logs=record['logs'])
            self.store.write(cid, 'accepted.json', accepted)
            self.store.accept(cid)
        self.log(f'[{repo.name}] accepted {cid} ({practice["family"]}, {spec.answer_kind})')

    # ---------- variations ----------
    async def vary_accepted(self, repo, target):
        seeds = [cid for cid, meta in self.candidates(repo.name, 'accepted') if meta['origin'] == 'seed'
                 and (not self.focus or self.store.read(cid, 'accepted.json')['family'] in self.focus)]
        jobs = []
        for cid in seeds:
            if self.progress(repo) >= target:
                break
            if self.store.read(cid, 'variations.json') is None:
                jobs.append(self.make_variations(repo, cid))
        new = [c for batch in await asyncio.gather(*jobs) for c in batch]
        await self.process_many(new)

    async def make_variations(self, repo, parent):
        spec = self.store.read(parent, 'spec.json')
        accepted = self.store.read(parent, 'accepted.json')
        record = self.store.read(parent, 'materialized.json')
        documents = {d.path: d.text for d in self.documents(repo)}
        from .repos import patch_files
        paths = [e['path'] for e in spec['evidence']] + record['setup_files'] + \
            (patch_files(spec['probe_patch']) if spec['probe_patch'] else []) + \
            (spec['context']['files'] if spec['context']['scope'] == 'files' else [])
        paths += [nodeid.split('::')[0] for nodeid in record['fail_to_pass'] + record['hidden_tests']]
        for e in spec['evidence']:
            module_dir = e['path'].rsplit('/', 1)[0]
            paths += [p for p in documents if p.startswith(module_dir + '/') and p.endswith('.py')][:6]
        files_text = files_block([(p, documents[p]) for p in dict.fromkeys(paths) if p in documents],
                                 self.config['generation']['generator_file_chars'])
        summary = dict(question=spec['question'], setting=spec['setting'], answer_kind=spec['answer_kind'],
                       answer_format=spec['answer_format'], rlm_behaviors=accepted['rlm_behaviors'],
                       behavior_rationale=accepted['behavior_rationale'], context=spec['context'],
                       verified_answer=str(accepted['answer'])[:3000], evidence=spec['evidence'],
                       setup_patch=spec['setup_patch'], probe_patch=spec['probe_patch'],
                       fail_to_pass=record['fail_to_pass'][:20], impact_tests=record['impact_tests'],
                       ground_truth_symbols=record['ground_truth_symbols'])
        count = self.config['generation']['variations_per_seed']
        summary['other_tasks_in_repository'] = [self.store.read(c, 'spec.json')['question'][:300]
                                                for c, _ in self.candidates(repo.name)
                                                if c != parent and self.store.read(c, 'spec.json')][-40:]
        # Resumable: suggestions are saved on the parent, and only children without a spec are edited.
        suggestions = self.store.read(parent, 'suggestions.json')
        if suggestions is None:
            async with self.candidate_slots:
                try:
                    suggestions = await self.roles.suggest(task_summary=summary, files_text=files_text, count=count)
                except Exception as exc:  # noqa: BLE001
                    self.store.write(parent, 'variations.json', dict(error=repr(exc)[:500], children=[]))
                    return []
            self.store.write(parent, 'suggestions.json', suggestions)
        children = []
        meta = self.store.read(parent, 'meta.json')
        for index, suggestion in enumerate(suggestions, 1):
            cid = f'{parent}-v{index}'
            if self.store.read(cid, 'spec.json') is not None or self.store.status(cid) != 'pending':
                if self.store.status(cid) == 'pending':
                    children.append(cid)
                continue
            self.store.write(cid, 'meta.json', dict(cid=cid, repo=repo.name, split=meta['split'], origin='variation',
                                                    round=meta['round'], parent_id=parent))
            self.store.write(cid, 'suggestion.json', suggestion)
            async with self.candidate_slots:
                try:
                    specs, invalid = await self.roles.edit(task_summary=summary, suggestion=suggestion,
                                                           files_text=files_text)
                except Exception as exc:  # noqa: BLE001
                    self.store.reject(cid, 'edit', 'editor_failed', repr(exc)[:500])
                    continue
            if not specs:
                detail = invalid[0]['error'] if invalid else 'editor declined the suggestion'
                self.store.reject(cid, 'edit', 'invalid_spec' if invalid else 'editor_declined', detail)
                continue
            self.store.write(cid, 'spec.json', specs[0].model_dump())
            children.append(cid)
        self.store.write(parent, 'variations.json', dict(children=children, suggestions=len(suggestions)))
        return children


def load_config(path):
    path = Path(path)
    return yaml.safe_load(path.read_text(encoding='utf-8')), path.resolve().parent.parent


def repractice(config, root):
    """Re-derive behavior labels of accepted tasks with the current practice analysis.

    Only labels change (established behaviors, family, rationale subset, tags);
    answers and verification are untouched. A task with no established behavior
    left is rejected as `practice_mismatch`.
    """
    root = Path(root)
    store = Store(root / config['work_dir'])
    harness = HarnessConfig.from_yaml(root / config['harness_config'])
    changed, rejected = [], []
    for cid in store.ids():
        if store.status(cid) != 'accepted':
            continue
        accepted = store.read(cid, 'accepted.json')
        spec = store.read(cid, 'spec.json')
        trace = read_json(store.path(cid, f"trajectory-{accepted['verification']['attempt']}.json"))
        result = check_behaviors(trace, spec['rlm_behaviors'], context_chars=accepted['context_chars'],
                                 practice=config['practice'], harness=harness,
                                 direct_read_max_chars=config['context']['direct_read_max_chars'])
        if not result['established']:
            store.reject(cid, 'practice', 'practice_mismatch', 'no intended behavior exhibited after re-analysis')
            rejected.append(cid)
            continue
        family = spec['primary_behavior'] if spec['primary_behavior'] in result['established'] else result['established'][0]
        result.update(family=family, relabeled_from=None if family == spec['primary_behavior'] else spec['primary_behavior'])
        store.write(cid, 'practice.json', result)
        updated = dict(accepted, family=family, rlm_behaviors=result['established'],
                       behavior_rationale={k: spec['behavior_rationale'][k] for k in result['established']},
                       tags=result['tags'], practice=dict(results=result['results'], facts=result['facts'],
                                                          coverage_lower_bound=result['coverage_lower_bound'],
                                                          relabeled_from=result['relabeled_from']))
        if updated != accepted:
            store.write(cid, 'accepted.json', updated)
            store.log('events.jsonl', dict(cid=cid, event='repracticed', before=accepted['rlm_behaviors'],
                                           after=result['established'], family=family))
            changed.append(dict(task_id=cid, before=accepted['rlm_behaviors'], after=result['established'],
                                family=family))
    return dict(changed=changed, rejected=rejected)
