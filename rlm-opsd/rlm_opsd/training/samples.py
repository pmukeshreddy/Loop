"""Turn-wise training samples built only from recorded inference token IDs."""
from dataclasses import dataclass
import math

from rlm_opsd.prompts.alignment import build_teacher_sequence


@dataclass(frozen=True)
class AlignedSample:
    student_ids: tuple[int, ...]
    teacher_ids: tuple[int, ...]
    student_positions: tuple[int, ...]
    teacher_positions: tuple[int, ...]
    target_ids: tuple[int, ...]
    inference_logprobs: tuple[float, ...]
    temperature: float


def _mask(values, length):
    if len(values)!=length or any(type(x) not in (bool,int) or x not in (0,1) for x in values):
        raise ValueError('invalid token mask or length')
    return tuple(bool(x) for x in values)


def samples_from_rollout(rollout, prefixes, *, max_seq_len):
    """Score each root completion once, keeping its actual recorded history.

    Per-turn samples do not require append-only history. Earlier turns in a
    later prompt are context, never additional targets. Missing server token
    records are an error; there is no text-tokenization fallback.
    """
    if rollout.get('error') is not None or not rollout.get('trajectory'):
        raise ValueError('rollout failed or has no trajectory')
    temperature=rollout.get('sampling_args',{}).get('temperature')
    if (type(temperature) not in (int,float) or not math.isfinite(temperature) or temperature<=0):
        raise ValueError('OPSD needs an explicit positive sampling temperature')
    if type(max_seq_len) is not int or max_seq_len<1:
        raise ValueError('max_seq_len must be positive')
    results=[]
    for step in rollout['trajectory']:
        tokens=step.get('tokens')
        required=('prompt_ids','prompt_mask','completion_ids','completion_mask','completion_logprobs')
        if not isinstance(tokens,dict) or any(tokens.get(key) is None for key in required):
            raise ValueError('original rollout IDs, masks and logprobs are required')
        if tokens.get('is_truncated') or tokens.get('overlong_prompt'):
            raise ValueError('clipped/overlong token records cannot preserve rollout alignment')
        prompt=tuple(tokens['prompt_ids']);completion=tuple(tokens['completion_ids'])
        student=prompt+completion
        teacher=build_teacher_sequence(student,student_prefix=prefixes.student_ids,
                                       teacher_prefix=prefixes.teacher_ids)
        if len(prompt)<len(prefixes.student_ids):
            raise ValueError('recorded prompt was clipped inside the initial prefix')
        if max(len(student),len(teacher))>max_seq_len:
            raise ValueError('aligned student/teacher sequence exceeds max_seq_len')
        if any(_mask(tokens['prompt_mask'],len(prompt))):
            raise ValueError('prompt/history tokens cannot be current completion targets')
        mask=_mask(tokens['completion_mask'],len(completion))
        logprobs=tuple(tokens['completion_logprobs'])
        if len(logprobs)!=len(completion) or any(
            type(x) not in (int,float) or not math.isfinite(x) or x>0 for x in logprobs):
            raise ValueError('completion logprobs must be finite, nonpositive and aligned')
        selected=[i for i,keep in enumerate(mask) if keep]
        offset=len(prefixes.teacher_ids)-len(prefixes.student_ids)
        positions=tuple(len(prompt)+i-1 for i in selected)
        results.append(AlignedSample(student,teacher,positions,tuple(i+offset for i in positions),
            tuple(completion[i] for i in selected),tuple(float(logprobs[i]) for i in selected),float(temperature)))
    return results
