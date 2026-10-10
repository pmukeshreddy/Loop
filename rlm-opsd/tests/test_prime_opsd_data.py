"""Token transport and native batch distribution, entirely on CPU."""
import copy

import msgspec
import pytest

from test_training_samples import rollout


def recorded_rollout():
    value = rollout()
    value['env_name'] = 'rlm_opsd'
    value['info']['opsd_prefixes'] = {'student_ids': [1, 2], 'teacher_ids': [1, 7, 8, 2]}
    return value


def test_original_multiturn_ids_survive_native_wire_and_distribution():
    from prime_rl.transport import TrainingBatch
    from prime_rl.trainer.batch import prepare_batch
    from rlm_opsd.training.prime_data import opsd_samples

    value = recorded_rollout()
    original = copy.deepcopy(value)
    samples = opsd_samples(value, max_seq_len=20)
    wire = msgspec.msgpack.encode(TrainingBatch(examples=samples, step=3))
    assert b'NEVER_COPY_TO_TRAINING' not in wire
    decoded = msgspec.msgpack.decode(wire, type=TrainingBatch)
    grid = prepare_batch(decoded.examples, 20, 3, [0, 0], 1)
    assert [len(rank) for rank in grid] == [1, 1, 1]
    batches = sorted((rank[0] for rank in grid[:2]), key=lambda b: len(b.input_ids))
    assert batches[0].input_ids == [1, 2, 3, 4]
    assert batches[0].opsd_teacher_ids == [1, 7, 8, 2, 3, 4]
    assert batches[0].opsd_teacher_positions == [3, 4]
    assert batches[1].opsd_teacher_positions == [7]
    assert batches[1].loss_mask == [False] * 6 + [True, False]
    assert not any(grid[2][0].loss_mask)
    assert grid[2][0].opsd_teacher_positions == []
    assert value == original


@pytest.mark.parametrize('fault', ['missing_prefix', 'bad_prefix', 'clipped', 'teacher_too_long'])
def test_alignment_cannot_be_lost_or_truncated(fault):
    from rlm_opsd.training.prime_data import opsd_samples
    value = recorded_rollout()
    limit = 20
    if fault == 'missing_prefix':
        del value['info']['opsd_prefixes']
    elif fault == 'bad_prefix':
        value['trajectory'][0]['tokens']['prompt_ids'][0] = 15
    elif fault == 'clipped':
        value['trajectory'][0]['tokens']['is_truncated'] = True
    else:
        limit = 8
    with pytest.raises(ValueError):
        opsd_samples(value, max_seq_len=limit)


def test_native_packer_refuses_to_clip_opsd_and_still_packs_ordinary_samples():
    from prime_rl.trainer.batch import prepare_batch
    from rlm_opsd.training.prime_data import opsd_samples
    samples = opsd_samples(recorded_rollout(), max_seq_len=20)
    with pytest.raises(ValueError, match='length|truncate|sequence'):
        prepare_batch(samples, 8, 1, [0, 0], 1)
    for sample in samples:
        sample.opsd_teacher_ids = None
        sample.opsd_teacher_positions = None
    grid = prepare_batch(samples, 20, 1, [0, 0], 1)
    assert len(grid[0]) == 1
    assert len(grid[0][0].input_ids) == 12


def test_orchestrator_cannot_reconstruct_missing_opsd_tokens():
    from prime_rl.orchestrator.trajectories import pretokenize_rollout_trajectory
    value = recorded_rollout()
    value['trajectory'][0]['tokens'] = None
    with pytest.raises(ValueError, match='original|recorded'):
        pretokenize_rollout_trajectory(value, tokenizer=object(), require_original=True)
