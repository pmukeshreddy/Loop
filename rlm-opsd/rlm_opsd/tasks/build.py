from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import copy
from datetime import date, timedelta
import json
import multiprocessing
from pathlib import Path
import random
import tempfile

from .codec import ENCODINGS
from .decontam import HeldoutIndex, decontaminate
from .generators import generate
from .models import FAMILIES, Task, TaskSpec, canonical, digest
from .verify import verify_answer


def _sample_knobs(settings, seed):
    """Resolve each knob independently of config order and worker scheduling."""
    sampled = {}
    for name, value in settings.items():
        rng = random.Random(f'{seed}:knob:{name}')
        if not isinstance(value, dict):
            sampled[name] = copy.deepcopy(value)
        elif set(value) == {'choices'}:
            choices = value['choices']
            if not isinstance(choices, list) or not choices:
                raise ValueError(f'knob {name}: choices must be a nonempty list')
            sampled[name] = copy.deepcopy(rng.choice(choices))
        elif set(value) == {'min', 'max'}:
            low, high = value['min'], value['max']
            if type(low) is int and type(high) is int and low <= high:
                sampled[name] = rng.randint(low, high)
            elif isinstance(low, str) and isinstance(high, str):
                try:
                    start, end = date.fromisoformat(low), date.fromisoformat(high)
                    if start > end:
                        raise ValueError('reversed date range')
                    sampled[name] = str(start + timedelta(days=rng.randint(0, (end - start).days)))
                except ValueError as exc:
                    raise ValueError(f'knob {name}: invalid ISO date range') from exc
            else:
                raise ValueError(f'knob {name}: min/max must be ordered integers or ISO dates')
        else:
            raise ValueError(f'knob {name}: use min/max or choices')
    return sampled


def plan_specs(config):
    required = ('seed', 'workers', 'size_buckets', 'structures', 'encodings', 'families',
                'splits', 'direct_read_max_chars', 'decontamination')
    if any(key not in config for key in required):
        raise ValueError('missing task configuration fields')
    if config['workers'] < 1 or not config['size_buckets'] or min(config['size_buckets']) <= 0:
        raise ValueError('positive worker count and sizes required')
    if set(config['families']) - set(FAMILIES) or not config['families']:
        raise ValueError('unknown or empty families')
    if set(config['splits']) != {'train', 'dev_behavior'}:
        raise ValueError('configure only train and dev_behavior splits')
    if set(config['structures']) - {'str', 'list'} or not config['structures']:
        raise ValueError('invalid structures')
    if set(config['encodings']) - set(ENCODINGS) or not config['encodings']:
        raise ValueError('invalid encodings')
    for count in [*config['families'].values(), *config['splits'].values()]:
        if not isinstance(count, int) or count < 1:
            raise ValueError('family weights and split counts must be positive integers')
    specs, excluded = [], []
    for family in sorted(config['families']):
        for bucket in config['size_buckets']:
            for structure in config['structures']:
                if family == 'repo_qa' and structure != 'list':
                    excluded.append(dict(family=family, bucket=bucket, structure=structure, reason='repo uses file lists'))
                    continue
                if family == 'small_context_control' and bucket >= config['direct_read_max_chars']:
                    excluded.append(dict(family=family, bucket=bucket, structure=structure, reason='exceeds direct-read limit'))
                    continue
                for split in ('train', 'dev_behavior'):
                    for instance in range(config['families'][family] * config['splits'][split]):
                        identity = [config['seed'], family, bucket, structure, split, instance]
                        seed = int(digest(canonical(identity))[:16], 16)
                        encoding = 'markdown' if family == 'repo_qa' else config['encodings'][len(specs) % len(config['encodings'])]
                        knobs = dict(target_chars=bucket, structure=structure, encoding=encoding,
                                     direct_read_max_chars=config['direct_read_max_chars'])
                        if config.get('labels'):
                            knobs['labels'] = copy.deepcopy(config['labels'])
                        knobs.update(_sample_knobs(config.get('family_knobs', {}).get(family, {}), seed))
                        specs.append(TaskSpec(family=family, knobs=knobs, seed=seed, split=split))
    return specs, excluded


def _generate_and_verify(job):
    spec, corpus = job
    task = generate(spec, corpus)
    recomputed = verify_answer(task, corpus)
    if recomputed != task.answer:
        raise ValueError(f'answer verification failed: {task.task_id}')
    return task


def _counts(tasks):
    counts = Counter((task.split, task.family, task.knobs['target_chars'],
                      'str' if isinstance(task.context, str) else 'list', task.knobs['encoding']) for task in tasks)
    return [dict(split=key[0], family=key[1], bucket=key[2], structure=key[3], encoding=key[4], count=value)
            for key, value in sorted(counts.items())]


def build_pool(config, output_dir, *, corpora, heldout=None):
    specs, excluded = plan_specs(config)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError('output directory must be empty; do not overwrite an existing task pool')
    jobs = [(spec, corpora.get(spec.split)) for spec in specs]
    if config['workers'] == 1:
        tasks = list(map(_generate_and_verify, jobs))
    else:
        # spawn works on both macOS and Linux and cannot inherit an RNG state.
        with ProcessPoolExecutor(max_workers=config['workers'], mp_context=multiprocessing.get_context('spawn')) as executor:
            tasks = list(executor.map(_generate_and_verify, jobs))
    if len({task.task_id for task in tasks}) != len(tasks):
        raise ValueError('duplicate task IDs in build plan')
    kept, decontamination = decontaminate(tasks, heldout or HeldoutIndex(), **config['decontamination'])
    report = dict(generated_total=len(tasks), written_total=len(kept), verified_total=len(tasks),
                  generated_grid=_counts(tasks), written_grid=_counts(kept), grid_exclusions=excluded,
                  source_imports={split: corpus.import_report for split, corpus in corpora.items()},
                  decontamination=decontamination, config=config)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.tasks-build-', dir=output.parent) as temporary:
        staging = Path(temporary) / 'pool'
        (staging / 'contexts').mkdir(parents=True)
        rows = []
        for task in kept:
            relative = f'contexts/{task.task_id}.json'
            (staging / relative).write_text(canonical(task.context) + '\n', encoding='utf-8')
            rows.append(task.manifest(relative))
        manifest = ''.join(canonical(row) + '\n' for row in rows)
        (staging / 'manifest.jsonl').write_text(manifest, encoding='utf-8')
        report['manifest_sha256'] = digest(manifest)
        (staging / 'build-report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        (staging / 'decontamination.json').write_text(json.dumps(decontamination, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            output.rmdir()  # only an empty user-selected output was accepted above
        staging.replace(output)
    return report


def _read_tasks(manifest_path):
    manifest = Path(manifest_path)
    seen = set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['task_id'] in seen:
            raise ValueError('duplicate manifest task ID')
        seen.add(row['task_id'])
        path = (manifest.parent / row['context_path']).resolve()
        if not path.is_relative_to(manifest.parent.resolve()):
            raise ValueError('context path escapes task pool')
        context = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(context, str) and not (isinstance(context, list) and all(isinstance(x, str) for x in context)):
            raise ValueError('invalid context type')
        size = len(context) if isinstance(context, str) else sum(map(len, context))
        if digest(canonical(context)) != row['context_sha256'] or size != row['context_chars']:
            raise ValueError('context checksum or length mismatch')
        if row['context_format'] != ('str' if isinstance(context, str) else 'list'):
            raise ValueError('context format mismatch')
        yield Task.from_manifest(row, context)


def load_tasks(manifest_path, *, split, inspection_only=False):
    if split not in ('train', 'dev_behavior', 'eval_heldout'):
        raise ValueError('select an explicit split')
    path = Path(manifest_path)
    if split != 'eval_heldout' and not inspection_only:
        report = json.loads((path.parent / 'build-report.json').read_text(encoding='utf-8'))
        if not report['decontamination']['coverage_complete']:
            raise ValueError('heldout coverage is incomplete; pool is inspection-only')
        if digest(path.read_text(encoding='utf-8')) != report['manifest_sha256']:
            raise ValueError('manifest changed after decontamination')
    for index, task in enumerate(_read_tasks(path)):
        if task.split != split:
            continue
        # Deliberately no answer/annotation/verification knobs in OPSD input.
        info = dict(task_id=task.task_id, family=task.family, domain=task.domain,
                    tags=task.tags, query=task.query, context=task.context)
        yield dict(example_id=index, prompt=[dict(role='user', content=task.query)], info=info)


def verify_pool(manifest_path, *, corpora):
    count = 0
    for task in _read_tasks(manifest_path):
        if task.split == 'eval_heldout':
            raise ValueError('generated-answer verifier cannot certify benchmark answers')
        if verify_answer(task, corpora.get(task.split)) != task.answer:
            raise ValueError(f'answer mismatch: {task.task_id}')
        count += 1
    return count
