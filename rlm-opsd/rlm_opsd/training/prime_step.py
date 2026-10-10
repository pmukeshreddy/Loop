"""OPSD loss inside the native model/head FSDP forward boundaries."""
import math

import torch
from torch import nn

from .jsd import chunked_jsd_loss, _settings
from .teacher import FORWARD_LOCK, frozen_teacher, prime_lora_api


class OpsdHead(nn.Linear):
    """Keep the ordinary weight key; project only selected assistant positions."""

    def configure(self, config):
        _settings(config.temperature, config.token_gate, config.gate_k)
        if type(config.chunk_size) is not int or config.chunk_size <= 0:
            raise ValueError('OPSD chunk_size must be positive')
        self.opsd_config = config
        self.opsd_context = None

    def forward(self, hidden_states, labels=None, temperature=None):
        if self.opsd_context is None:
            raise RuntimeError('OPSD head requires an aligned forward context')
        positions, teacher, targets = self.opsd_context
        hidden = hidden_states[0, positions]
        if teacher is None:
            return {'teacher_hidden': hidden.detach()}
        config = self.opsd_config
        mask = torch.ones(hidden.shape[0], dtype=torch.bool, device=hidden.device)
        loss = chunked_jsd_loss(hidden, teacher, self.weight, mask, target_ids=targets,
            chunk_size=config.chunk_size, temperature=config.temperature,
            token_gate=config.token_gate, gate_k=config.gate_k)
        # Logging also projects in chunks; no full-sequence vocabulary tensor.
        logprobs, entropies = [], []
        with torch.no_grad():
            for start in range(0, hidden.shape[0], config.chunk_size):
                logp = (nn.functional.linear(hidden[start:start + config.chunk_size], self.weight).float()
                        / config.temperature).log_softmax(-1)
                ids = targets[start:start + config.chunk_size]
                logprobs.append(logp.gather(1, ids[:, None]).squeeze(1))
                entropies.append(-(logp.exp() * logp).sum(-1))
        empty = hidden.new_empty((0,), dtype=torch.float32)
        return {'loss': loss, 'logprobs': torch.cat(logprobs) if logprobs else empty,
                'entropy': torch.cat(entropies) if entropies else empty}


def install_opsd_head(model, config):
    """Called by setup_model before LoRA, activation checkpointing, and FSDP."""
    old = model.lm_head
    if not isinstance(old, nn.Linear) or old.bias is not None:
        raise ValueError('OPSD requires a linear output head without bias')
    for cfg in (getattr(model, 'config', None), getattr(getattr(model, 'config', None), 'text_config', None)):
        if getattr(cfg, 'final_logit_softcapping', None):
            raise ValueError('OPSD does not support softcapped heads')
    with torch.device('meta'):
        head = OpsdHead(old.in_features, old.out_features, bias=False)
    head.weight = old.weight
    head.configure(config)
    model.lm_head = head


def opsd_forward(model, micro_batch, *, loss_scale, api=None):
    """Return a scaled loss; native train.py owns backward and optimizer state.

    The teacher runs first so no outstanding student graph is disturbed by an
    extra FSDP forward. Both passes enter the outer model and head via __call__.
    """
    api = api or prime_lora_api()
    head = model.lm_head
    if not isinstance(head, OpsdHead):
        raise ValueError('OPSD output head was not installed before FSDP')
    if not math.isfinite(loss_scale) or loss_scale <= 0:
        raise ValueError('OPSD loss_scale must be positive and finite')
    if micro_batch.get('sft_loss'):
        raise ValueError('SFT is forbidden during OPSD')
    device = next(model.parameters()).device
    ids = micro_batch['input_ids'].to(device)
    mask = micro_batch['loss_mask'].to(device)
    if ids.ndim != 2 or ids.shape[0] != 1 or mask.shape != ids.shape or mask.dtype != torch.bool:
        raise ValueError('OPSD requires one aligned sequence per microbatch')
    positions = micro_batch['position_ids'].to(device)
    if not torch.equal(positions, torch.arange(ids.shape[1], device=device)[None]):
        raise ValueError('OPSD requires an unpacked, unpadded sequence')
    targets_at = mask[0].nonzero().flatten()
    if (targets_at == 0).any():
        raise ValueError('first token cannot be a causal target')
    teacher_ids = micro_batch.get('opsd_teacher_ids')
    teacher_at = micro_batch.get('opsd_teacher_positions')
    if not teacher_ids or teacher_at is None or len(teacher_at) != targets_at.numel():
        raise ValueError('OPSD teacher alignment metadata is missing')
    teacher_ids = torch.tensor([teacher_ids], device=device, dtype=torch.long)
    teacher_at = torch.tensor(teacher_at, device=device, dtype=torch.long)
    if ((teacher_at < 0) | (teacher_at + 1 >= teacher_ids.shape[1])).any():
        raise ValueError('teacher causal positions are out of bounds')
    prefix_lengths = micro_batch.get('opsd_prefix_lengths')
    if prefix_lengths is None or len(prefix_lengths) != 2:
        raise ValueError('OPSD prefix alignment metadata is missing')
    student_prefix, teacher_prefix = prefix_lengths
    if not (0 < student_prefix <= ids.shape[1] and 0 < teacher_prefix <= teacher_ids.shape[1]):
        raise ValueError('invalid prefix alignment lengths')
    if not torch.equal(ids[0, student_prefix:], teacher_ids[0, teacher_prefix:]):
        raise ValueError('student/teacher suffix alignment differs')
    if not torch.equal(teacher_at, targets_at - 1 + teacher_prefix - student_prefix):
        raise ValueError('teacher causal alignment differs')
    targets = ids[0, targets_at]
    if not torch.equal(targets, teacher_ids[0, teacher_at + 1]):
        raise ValueError('teacher target alignment differs')
    temperatures = micro_batch['temperatures'].to(device)[mask]
    if not torch.allclose(temperatures, torch.full_like(temperatures, head.opsd_config.temperature)):
        raise ValueError('rollout temperature differs from OPSD objective')
    with FORWARD_LOCK:
        api.base.set_lora_num_tokens(micro_batch['lora_num_tokens'].to(device))
        try:
            head.opsd_context = (teacher_at, None, targets)
            with frozen_teacher(model, teacher_ids.shape[1], api=api, allow_fsdp=True):
                teacher = model(input_ids=teacher_ids,
                    position_ids=torch.arange(teacher_ids.shape[1], device=device)[None],
                    use_cache=False)['teacher_hidden']
            head.opsd_context = (targets_at - 1, teacher.detach(), targets)
            output = model(input_ids=ids, position_ids=positions, use_cache=False)
            output['loss'] = output['loss'] * (targets.numel() / loss_scale)
            return output
        finally:
            head.opsd_context = None


def global_loss_scale(local_tokens, *, device, group=None):
    """FSDP averages gradients: divide each local sum by global_tokens/world."""
    import torch.distributed as dist
    count = torch.tensor(float(local_tokens), dtype=torch.float64, device=device)
    world_size = 1
    if dist.is_initialized():
        dist.all_reduce(count, group=group)
        world_size = dist.get_world_size(group)
    return max(count.item(), 1.) / world_size
