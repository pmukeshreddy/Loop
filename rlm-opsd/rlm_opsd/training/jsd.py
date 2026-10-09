"""Exact beta=0.5 Jensen-Shannon divergence for root assistant targets."""
import math

import torch
from torch.autograd.function import once_differentiable
from torch.nn import functional as F


def _settings(temperature, token_gate, gate_k):
    for name, value in (('temperature', temperature), ('gate_k', gate_k)):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(name + ' must be positive and finite')
    if type(token_gate) is not bool:
        raise ValueError('token_gate must be boolean')


def _pair(student, teacher, mask):
    if (student.ndim != 2 or teacher.shape != student.shape or student.shape[1] == 0
            or not student.is_floating_point() or student.dtype != teacher.dtype
            or student.device != teacher.device):
        raise ValueError('student/teacher must be matching floating [tokens, features] tensors')
    if mask.shape != student.shape[:1] or mask.dtype != torch.bool or mask.device != student.device:
        raise ValueError('mask must be an aligned boolean tensor')


def _targets(target_ids, mask, vocab_size, token_gate):
    if target_ids is None:
        if token_gate:
            raise ValueError('token gate requires aligned target IDs')
        return None
    if (target_ids.shape != mask.shape or target_ids.dtype != torch.long
            or target_ids.device != mask.device):
        raise ValueError('target IDs must be aligned int64 tokens')
    selected = target_ids[mask]
    if ((selected < 0) | (selected >= vocab_size)).any():
        raise ValueError('selected target ID outside vocabulary')
    return selected


def _work_dtype(tensor):
    return torch.float64 if tensor.dtype == torch.float64 else torch.float32


def _token_losses(student, teacher, targets, temperature, token_gate, gate_k):
    if not torch.isfinite(student).all() or not torch.isfinite(teacher).all():
        raise ValueError('nonfinite logits at selected assistant positions')
    dtype = _work_dtype(student)
    limit = torch.finfo(dtype).max
    if temperature < 1 / limit or temperature > limit or gate_k > limit:
        raise ValueError('normalization/gate scalar exceeds working precision')
    log_s = (student.to(dtype) / temperature).log_softmax(-1)
    log_t = (teacher.detach().to(dtype) / temperature).log_softmax(-1)
    if not torch.isfinite(log_s).all() or not torch.isfinite(log_t).all():
        raise ValueError('logit normalization exceeds working precision; check logits and temperature')
    log_m = torch.logaddexp(log_s, log_t) - math.log(2)
    values = .5 * ((log_s.exp() * (log_s - log_m)).sum(-1)
                   + (log_t.exp() * (log_t - log_m)).sum(-1))
    if token_gate:
        delta = (log_t.gather(1, targets[:, None]) - log_s.gather(1, targets[:, None])).squeeze(1)
        values = values * torch.sigmoid(gate_k * delta).detach()
    return values


def masked_jsd_loss(student_logits, teacher_logits, mask, *, target_ids=None,
                    temperature=1.0, token_gate=False, gate_k=1.0):
    """Dense correctness reference; trainer uses the chunked projection path.

    Beta is fixed at 0.5. Gate weights do not change the selected-token
    denominator and receive no gradients. Teacher tensors are always detached.
    """
    _settings(temperature, token_gate, gate_k)
    _pair(student_logits, teacher_logits, mask)
    targets = _targets(target_ids, mask, student_logits.shape[-1], token_gate)
    student = student_logits[mask]
    if student.shape[0] == 0:
        return student.to(_work_dtype(student)).sum() * 0
    return _token_losses(student, teacher_logits[mask], targets, temperature, token_gate, gate_k).mean()


def _projected_loss(student, teacher, weight, targets, temperature, token_gate, gate_k):
    # Preserve the frozen head's native dtype; do not copy its V*H weights to
    # FP32. Normalize only the chunk logits in FP32 (float64 for numerical tests).
    # Explicitly disable ambient autocast so backward recomputation uses the
    # same projection arithmetic as forward.
    with torch.autocast(device_type=student.device.type, enabled=False):
        s = F.linear(student, weight)
        t = F.linear(teacher, weight)
        return _token_losses(s, t, targets, temperature, token_gate, gate_k).sum()


class _ChunkedJSD(torch.autograd.Function):
    @staticmethod
    def forward(ctx, student, teacher, weight, targets, chunk_size, temperature, token_gate, gate_k):
        ctx.save_for_backward(student, teacher, weight, targets)
        ctx.settings = (chunk_size, temperature, token_gate, gate_k)
        total = student.new_zeros((), dtype=_work_dtype(student))
        for start in range(0, student.shape[0], chunk_size):
            end = start + chunk_size
            ids = None if targets is None else targets[start:end]
            total += _projected_loss(student[start:end], teacher[start:end], weight, ids,
                                     temperature, token_gate, gate_k)
        return total

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_output):
        student, teacher, weight, targets = ctx.saved_tensors
        chunk_size, temperature, token_gate, gate_k = ctx.settings
        gradient = torch.empty_like(student)
        # Rebuild and free one projection/loss graph at a time. The backbone
        # graph is traversed only after this returns the complete hidden VJP.
        for start in range(0, student.shape[0], chunk_size):
            end = start + chunk_size
            ids = None if targets is None else targets[start:end]
            with torch.enable_grad():
                hidden = student[start:end].detach().requires_grad_(True)
                value = _projected_loss(hidden, teacher[start:end], weight, ids,
                                        temperature, token_gate, gate_k)
                (chunk_gradient,) = torch.autograd.grad(value, hidden, grad_outputs=grad_output)
            gradient[start:end] = chunk_gradient
        return gradient, None, None, None, None, None, None, None


def chunked_jsd_loss(student_hidden, teacher_hidden, weight, mask, *, target_ids=None,
                     chunk_size=64, temperature=1.0, token_gate=False, gate_k=1.0):
    """Project selected rows only; O(chunk_size*vocab) projection/loss workspace.

    Retains selected hidden states and a reference to the frozen ordinary
    linear head. Returns first-order student gradients only. Backbone memory,
    head weights and O(selected_tokens*hidden) state are separate from this bound.
    """
    _settings(temperature, token_gate, gate_k)
    _pair(student_hidden, teacher_hidden, mask)
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError('chunk_size must be a positive integer')
    if (weight.ndim != 2 or weight.shape[1] != student_hidden.shape[1] or weight.shape[0] == 0
            or weight.device != student_hidden.device or weight.dtype != student_hidden.dtype
            or weight.requires_grad):
        raise ValueError('head must be a frozen matching [vocab, hidden] weight tensor')
    targets = _targets(target_ids, mask, weight.shape[0], token_gate)
    student = student_hidden[mask]
    if student.shape[0] == 0:
        return student.to(_work_dtype(student)).sum() * 0
    teacher = teacher_hidden.detach()[mask]
    return _ChunkedJSD.apply(student, teacher, weight, targets, chunk_size,
                             temperature, token_gate, gate_k) / student.shape[0]
