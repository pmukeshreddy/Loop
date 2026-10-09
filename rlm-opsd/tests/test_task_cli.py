import hashlib
import json
from pathlib import Path
import subprocess
import sys

import yaml

from test_task_pipeline import config


def test_cli_prepares_pinned_inputs_builds_and_verifies_without_network(tmp_path):
    source = tmp_path / 'origin.csv'
    source.write_text('text,category\nMy card is still in the post,card_arrival\nWhat rate converts euros,exchange_rate\n')
    questions = tmp_path / 'questions.json'
    questions.write_text(json.dumps([dict(id='1', question='A reserved query?', answer='', type='list_of_answers')]))
    cfg = config()
    cfg['classification_sources'] = {split: dict(path=str(tmp_path / f'{split}.csv'), url=source.as_uri(),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(), revision='fixture', partition=split,
        ambiguity_policy='drop') for split in ('train', 'dev_behavior')}
    cfg['heldout_question_sources'] = [dict(benchmark='oolong_pairs', path=str(tmp_path / 'pairs.json'),
        url=questions.as_uri(), sha256=hashlib.sha256(questions.read_bytes()).hexdigest(), revision='fixture', license='MIT')]
    cfg['heldout_index'] = str(tmp_path / 'index.json')
    cfg_path = tmp_path / 'tasks.yaml'
    cfg_path.write_text(yaml.safe_dump(cfg))
    command = [sys.executable, '-m', 'rlm_opsd.tasks']
    prepared = subprocess.run(command + ['prepare', '--config', str(cfg_path)], capture_output=True, text=True)
    assert prepared.returncode == 0, prepared.stderr
    assert json.loads((tmp_path / 'index.json').read_text())['coverage']['oolong_pairs']['complete'] is False
    target = tmp_path / 'pool'
    built = subprocess.run(command + ['build', '--config', str(cfg_path), '--output', str(target)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    report = json.loads(built.stdout)
    assert report['generated_total'] == 40 and report['coverage_complete'] is False
    verified = subprocess.run(command + ['verify', '--config', str(cfg_path), '--manifest', str(target / 'manifest.jsonl')], capture_output=True, text=True)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)['verified_total'] == 40
    # A cached corrupt source cannot be used or silently accepted.
    (tmp_path / 'train.csv').write_text('corrupted')
    rejected = subprocess.run(command + ['build', '--config', str(cfg_path), '--output', str(tmp_path / 'bad')], capture_output=True, text=True)
    assert rejected.returncode != 0 and 'checksum' in rejected.stderr
    assert not (tmp_path / 'bad').exists()


def test_empty_or_forged_coverage_cannot_release_training_pool(tmp_path):
    from rlm_opsd.tasks.decontam import HeldoutIndex, HeldoutRecord
    from rlm_opsd.tasks.models import BENCHMARKS
    index = HeldoutIndex(coverage={name: dict(complete=True, revision='r', record_count=0) for name in BENCHMARKS})
    assert set(index.missing()) == set(BENCHMARKS)
    index.records = [HeldoutRecord(benchmark=name, task_id='x', query='Question', source_refs=[]) for name in BENCHMARKS]
    for name in BENCHMARKS:
        index.coverage[name]['record_count'] = 1
    assert set(index.missing()) == set(BENCHMARKS)


def test_default_grid_covers_requested_sizes_and_family_eligibility():
    from rlm_opsd.tasks.build import plan_specs
    cfg = yaml.safe_load(Path('configs/tasks.yaml').read_text())
    tasks, excluded = plan_specs(cfg)
    assert cfg['size_buckets'] == [8192, 32768, 131072, 524288, 2097152, 8388608]
    assert {s.family for s in tasks} == set(cfg['families'])
    for family in cfg['families']:
        expected = {size for size in cfg['size_buckets'] if family != 'small_context_control' or size < cfg['direct_read_max_chars']}
        for split in ['train', 'dev_behavior']:
            assert {s.knobs['target_chars'] for s in tasks if s.family == family and s.split == split} == expected
    assert excluded
