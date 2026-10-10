"""Original rollout tokens carried through prime-rl's native transport."""
from types import SimpleNamespace

from .samples import samples_from_rollout


def opsd_samples(rollout, *, max_seq_len):
    from prime_rl.transport.types import TrainingSample

    raw = rollout.get('info', {}).get('opsd_prefixes')
    if not isinstance(raw, dict) or set(raw) != {'student_ids', 'teacher_ids'}:
        raise ValueError('OPSD requires recorded student/teacher prefixes')
    prefixes = SimpleNamespace(**{k: tuple(v) for k, v in raw.items()})
    aligned = samples_from_rollout(rollout, prefixes, max_seq_len=max_seq_len)
    result = []
    for step, sample in zip(rollout['trajectory'], aligned):
        tokens = step['tokens']
        result.append(TrainingSample(
            prompt_ids=list(tokens['prompt_ids']), prompt_mask=[False] * len(tokens['prompt_ids']),
            completion_ids=list(tokens['completion_ids']),
            completion_mask=[bool(v) for v in tokens['completion_mask']],
            completion_logprobs=list(tokens['completion_logprobs']),
            completion_temperatures=[sample.temperature] * len(tokens['completion_ids']),
            env_name=rollout['env_name'], advantage=0., reward=0.,
            opsd_teacher_ids=list(sample.teacher_ids),
            opsd_teacher_positions=list(sample.teacher_positions),
            opsd_prefix_lengths=[len(prefixes.student_ids), len(prefixes.teacher_ids)],
        ))
    return result


def validate_opsd_sample(sample, seq_len):
    if sample.opsd_teacher_ids is None:
        return
    if sample.sft_loss or sample.teacher_logprobs is not None or sample.pixel_values is not None:
        raise ValueError('OPSD requires text-only local teacher scoring without SFT')
    if max(len(sample.prompt_ids) + len(sample.completion_ids), len(sample.opsd_teacher_ids)) > seq_len:
        raise ValueError('OPSD sequence length exceeds limit; truncation is forbidden')
    if sample.opsd_teacher_positions is None or sample.opsd_prefix_lengths is None:
        raise ValueError('OPSD alignment metadata is missing')
