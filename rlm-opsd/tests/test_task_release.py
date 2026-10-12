"""Release of accepted candidates through the existing answer-free OPSD loader."""
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def accepted(cid, split, repo, answer, family='inspect_locate'):
    return dict(
        task_id=cid, split=split, family=family, rlm_behaviors=[family], behavior_rationale={family: 'why ' * 10},
        intended_behaviors=[family, 'persistent_state'], setting='change_impact', query=f'Which tests break? ({cid})',
        answer=answer, answer_type='test_ids', answer_format='set', answer_key=json.dumps(answer), size_bucket=65536,
        context_chars=20, tags=['large_context', 'sparse'], parent_id=None, variation=None, origin='seed',
        repo=dict(name=repo, url='u', ref='1', commit='0' * 40, license='MIT'),
        verification=dict(method='impact', attempt=1, fail_to_pass=[], hidden_tests=[], pass_to_pass_count=3,
                          impact_tests=answer, ground_truth_symbols=[], evidence={}, stability_runs=3),
        practice=dict(results={}, facts={}, coverage_lower_bound=None), review=dict(notes='ok', behavior_notes={}),
        documents=['pkg/a.py'], logs=[])


def make_work(tmp_path, *, coverage_complete=True):
    config = yaml.safe_load((ROOT / 'configs/tasks.yaml').read_text())
    config['work_dir'] = str(tmp_path / 'work')
    config['heldout'] = dict(config['heldout'], index=str(tmp_path / 'index.json'))
    from rlm_opsd.tasks.decontam import HeldoutIndex, HeldoutRecord
    from rlm_opsd.tasks.models import BENCHMARKS
    records = [HeldoutRecord(b, f'{b}-1', f'reserved {b} question about an unrelated corpus',
                             [dict(dataset=b, item_id='1', revision='r', sha256='0' * 64)]) for b in BENCHMARKS]
    coverage = {b: dict(complete=coverage_complete, record_count=1, revision='r') for b in BENCHMARKS}
    HeldoutIndex(records=records, coverage=coverage).write(tmp_path / 'index.json')
    from rlm_opsd.tasks.store import Store, write_json
    work = tmp_path / 'work'
    store = Store(work)
    write_json(work / 'splits.json', dict(assignment={'o/train': 'train', 'o/dev': 'dev_behavior'}))
    write_json(work / 'sources.lock.json', {'o/train': dict(tree_sha256='t'), 'o/dev': dict(tree_sha256='d')})
    write_json(work / 'run.json', dict(skills={'solver': 'abc'}))
    shared = ['# File: pkg/a.py\nA = 1\n', '# Log: pytest\nFAILED']
    for cid, split, repo, answer in [('o-train-r01-00', 'train', 'o/train', ['tests/t.py::test_a']),
                                     ('o-train-r01-01', 'train', 'o/train', ['tests/t.py::test_b']),
                                     ('o-dev-r01-00', 'dev_behavior', 'o/dev', ['tests/t.py::test_c'])]:
        store.write(cid, 'meta.json', dict(cid=cid, repo=repo, split=split, origin='seed', round=1, parent_id=None))
        store.write(cid, 'spec.json', dict(question='q', setup_patch=None, probe_patch='--- a/x\n+++ b/x\n',
                                           hidden_tests_patch=None))
        store.write(cid, 'accepted.json', accepted(cid, split, repo, answer))
        store.write(cid, 'context.json', shared)
        store.write(cid, 'truth.json', dict(kind='impact', answer=answer))
        store.write(cid, 'trajectory-1.json', dict(turns=[]))
        store.accept(cid)
    store.write('o-train-r01-02', 'meta.json', dict(cid='o-train-r01-02', repo='o/train', split='train',
                                                    origin='seed', round=1, parent_id=None))
    store.reject('o-train-r01-02', 'verify', 'reference_answer_incorrect', 'mismatch')
    return config


def test_build_releases_accepted_tasks_with_references_and_answer_free_loader(tmp_path):
    from rlm_opsd.tasks.build import build_pool, load_tasks
    config = make_work(tmp_path)
    report = build_pool(config, ROOT, tmp_path / 'pool', verify_runs=0)
    assert report['written_total'] == 3 and report['written_by_split'] == {'train': 2, 'dev_behavior': 1}
    assert report['rejections']['total'] == 1 and report['rejections']['by_stage_code'][0]['code'] == \
        'reference_answer_incorrect'
    pool = tmp_path / 'pool'
    rows = [json.loads(line) for line in (pool / 'manifest.jsonl').read_text().splitlines()]
    assert len({r['context_path'] for r in rows}) == 1  # identical contexts are stored once
    assert all((pool / r['reference_path'] / 'reference.json').exists() for r in rows)
    assert all((pool / r['reference_path'] / 'probe.patch').exists() for r in rows)
    assert {r['family'] for r in rows} == {'inspect_locate'} and rows[0]['domain'] == 'deepswe'
    assert rows[0]['source_refs'][0]['dataset'] == 'github'
    train = list(load_tasks(pool / 'manifest.jsonl', split='train'))
    assert len(train) == 2
    for row in train:
        text = json.dumps(row)
        assert 'test_a' not in text and 'test_b' not in text  # no answers or references in OPSD input
        assert set(row['info']) == {'task_id', 'family', 'domain', 'tags', 'query', 'context'}
        assert row['info']['context'][0].startswith('# File: pkg/a.py')
    assert len(list(load_tasks(pool / 'manifest.jsonl', split='dev_behavior'))) == 1
    with pytest.raises(ValueError, match='empty'):
        build_pool(config, ROOT, pool, verify_runs=0)


def test_loader_refuses_incomplete_coverage_and_tampered_manifests(tmp_path):
    from rlm_opsd.tasks.build import build_pool, load_tasks
    config = make_work(tmp_path, coverage_complete=False)
    build_pool(config, ROOT, tmp_path / 'pool', verify_runs=0)
    manifest = tmp_path / 'pool/manifest.jsonl'
    with pytest.raises(ValueError, match='inspection-only'):
        list(load_tasks(manifest, split='train'))
    assert len(list(load_tasks(manifest, split='train', inspection_only=True))) == 2
    with pytest.raises(ValueError, match='explicit split'):
        list(load_tasks(manifest, split='all'))
    rows = manifest.read_text().splitlines()
    tampered = json.loads(rows[0])
    tampered['context_sha256'] = '0' * 64
    manifest.write_text('\n'.join([json.dumps(tampered)] + rows[1:]) + '\n')
    with pytest.raises(ValueError, match='checksum'):
        list(load_tasks(manifest, split='train', inspection_only=True))


def test_build_rejects_split_that_differs_from_repository_assignment(tmp_path):
    from rlm_opsd.tasks.build import build_pool
    from rlm_opsd.tasks.store import Store
    config = make_work(tmp_path)
    store = Store(tmp_path / 'work')
    leaked = store.read('o-dev-r01-00', 'accepted.json')
    leaked['split'] = 'train'
    store.write('o-dev-r01-00', 'accepted.json', leaked)
    with pytest.raises(ValueError, match='split differs'):
        build_pool(config, ROOT, tmp_path / 'pool', verify_runs=0)


def test_opsd_environment_still_strips_answers_and_rejects_reward_scoring():
    source = (ROOT / 'rlm_opsd/training/prime_env.py').read_text()
    assert "record['answer'] = ''" in source and "OPSD does not score rewards" in source


def test_reopened_rejections_are_not_counted_as_final(tmp_path):
    from rlm_opsd.tasks.build import _rejections
    from rlm_opsd.tasks.store import Store, reopen
    make_work(tmp_path)
    store = Store(tmp_path / 'work')
    store.write('o-train-r01-03', 'meta.json', dict(cid='o-train-r01-03', repo='o/train', split='train',
                                                    origin='seed', round=1, parent_id=None))
    store.write('o-train-r01-03', 'practice.json', {})
    store.reject('o-train-r01-03', 'practice', 'reference_executed_repository', 'pytest')
    assert _rejections(tmp_path / 'work')['total'] == 2
    assert reopen(tmp_path / 'work', {'reference_executed_repository'}) == ['o-train-r01-03']
    assert store.status('o-train-r01-03') == 'pending' and not store.path('o-train-r01-03', 'practice.json').exists()
    assert _rejections(tmp_path / 'work')['total'] == 1
    import pytest
    with pytest.raises(ValueError, match='cannot be reopened'):
        reopen(tmp_path / 'work', {'reference_answer_incorrect'})
