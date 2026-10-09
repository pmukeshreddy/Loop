"""Metadata geometry for detector coverage, without retaining context contents."""

import pytest


def legacy_trace():
    return dict(task_id='fixture', family='sparse_retrieval', domain='test', tags=['sparse'])


def test_legacy_trajectory_accepts_missing_geometry_without_inventing_zero_length():
    from rlm_opsd.harness.trajectory import EpisodeTrace

    trace = EpisodeTrace.model_validate(legacy_trace())
    assert trace.context_metadata is None
    assert trace.size_bucket is None
    assert trace.turns == []


@pytest.mark.parametrize('metadata', [
    dict(context_type='str', context_total_length=11, context_lengths=[]),
    dict(context_type='str', context_total_length=0, context_lengths=[]),
    dict(context_type='list', context_total_length=11, context_lengths=[4, 7]),
    dict(context_type='list', context_total_length=0, context_lengths=[]),
    dict(context_type='list', context_total_length=3, context_lengths=[0, 3, 0]),
])
def test_valid_context_geometry_round_trips_as_metadata_only(metadata):
    from rlm_opsd.harness.trajectory import EpisodeTrace

    raw = {**legacy_trace(), 'context_metadata': metadata, 'size_bucket': 8192}
    trace = EpisodeTrace.model_validate(raw)
    serialized = trace.model_dump(mode='json')
    assert serialized['context_metadata'] == metadata
    assert serialized['size_bucket'] == 8192


@pytest.mark.parametrize('metadata,reason', [
    (dict(context_type='list', context_total_length=8, context_lengths=[3, 4]), 'sum'),
    (dict(context_type='list', context_total_length=1, context_lengths=[]), 'sum'),
    (dict(context_type='str', context_total_length=8, context_lengths=[8]), 'empty'),
])
def test_inconsistent_geometry_cannot_be_used_as_a_coverage_denominator(metadata, reason):
    from rlm_opsd.harness.trajectory import EpisodeTrace

    with pytest.raises(ValueError, match=reason):
        EpisodeTrace.model_validate({**legacy_trace(), 'context_metadata': metadata})


@pytest.mark.parametrize('changes', [
    {'context_type': 'tuple'}, {'context_total_length': -1}, {'context_total_length': True},
    {'context_total_length': 1.5}, {'context_total_length': '4'},
    {'context_lengths': [-1, 5]}, {'context_lengths': [True, 3]},
    {'context_lengths': [1.5, 2.5]}, {'context_lengths': ['4']},
    {'context': 'PRIVATE'}, {'context_prefix': 'PRIVATE'},
])
def test_metadata_rejects_invalid_types_lengths_and_accidental_context_contents(changes):
    from rlm_opsd.harness.trajectory import ContextMetadataTrace

    metadata = dict(context_type='list', context_total_length=4, context_lengths=[4])
    with pytest.raises(ValueError):
        ContextMetadataTrace.model_validate({**metadata, **changes})


@pytest.mark.parametrize('omitted', ['context_type', 'context_total_length', 'context_lengths'])
def test_partial_geometry_is_rejected_instead_of_filling_unknown_fields(omitted):
    from rlm_opsd.harness.trajectory import ContextMetadataTrace

    metadata = dict(context_type='list', context_total_length=4, context_lengths=[4])
    del metadata[omitted]
    with pytest.raises(ValueError, match=omitted):
        ContextMetadataTrace.model_validate(metadata)


@pytest.mark.parametrize('size_bucket', [0, 8192, None])
def test_size_bucket_is_optional_and_accepts_known_nonnegative_character_sizes(size_bucket):
    from rlm_opsd.harness.trajectory import EpisodeTrace

    trace = EpisodeTrace.model_validate({**legacy_trace(), 'size_bucket': size_bucket})
    assert trace.size_bucket == size_bucket


@pytest.mark.parametrize('size_bucket', [-1, True, 8192.5, '8192'])
def test_size_bucket_rejects_invalid_values(size_bucket):
    from rlm_opsd.harness.trajectory import EpisodeTrace

    with pytest.raises(ValueError, match='size_bucket'):
        EpisodeTrace.model_validate({**legacy_trace(), 'size_bucket': size_bucket})


@pytest.mark.parametrize('context,expected,size_bucket', [
    ('TOP_SECRET🦉', dict(context_type='str', context_total_length=11, context_lengths=[]), 8192),
    (['TOP_', 'SECRET🦉'], dict(context_type='list', context_total_length=11, context_lengths=[4, 7]), None),
    ([], dict(context_type='list', context_total_length=0, context_lengths=[]), 0),
])
def test_episode_populates_geometry_and_bucket_without_logging_context_or_prefix(
        tmp_path, context, expected, size_bucket):
    from rlm_opsd.harness import Episode, HarnessConfig

    info = {**legacy_trace(), 'context': context, 'query': 'Find a value'}
    if size_bucket is not None:
        info['size_bucket'] = size_bucket
    episode = Episode(config=HarnessConfig(prefix_chars=4), info=info,
                      frozen_client=object(), frozen_model='unused-fixture', log_dir=tmp_path)
    serialized = episode.trace.model_dump(mode='json')
    assert serialized['context_metadata'] == expected
    assert serialized['size_bucket'] == size_bucket
    assert 'context' not in serialized
    assert 'context_prefix' not in serialized['context_metadata']
    assert 'TOP_' not in episode.trace.model_dump_json()
    assert 'SECRET' not in episode.trace.model_dump_json()
