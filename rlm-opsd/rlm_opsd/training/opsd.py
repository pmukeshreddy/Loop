"""OPSD correctness trainer with exact, chunked full-vocabulary JSD."""
import math

import torch
from torch import nn

from .jsd import chunked_jsd_loss, _settings
from .teacher import FORWARD_LOCK, checked_adapters, frozen_teacher, prime_lora_api


def backbone_hidden(model, input_ids, position_ids):
    """Use the same backbone boundary as pinned prime-rl's head-patched forward.

    Explicit positions are built for each prefix length. No language-model
    head is invoked and no sequence-by-vocabulary tensor is created here.
    """
    output = model.model(input_ids=input_ids, position_ids=position_ids, use_cache=False)
    hidden = output.last_hidden_state
    if hidden.ndim != 3 or hidden.shape[:2] != input_ids.shape:
        raise ValueError('backbone must return [batch, sequence, hidden] states')
    return hidden


def _head_weight(model):
    head = getattr(model, 'lm_head', None)
    if (type(head) is not nn.Linear or head.bias is not None
            or 'forward' in head.__dict__ or head.weight.requires_grad):
        raise ValueError('OPSD requires a frozen ordinary linear head without bias')
    config = getattr(model, 'config', None)
    for cfg in (config, getattr(config, 'text_config', None)):
        if getattr(cfg, 'final_logit_softcapping', None):
            raise ValueError('softcapped vocabulary heads are unsupported')
    return head.weight


def _selected_hidden(hidden, positions):
    if hidden.ndim != 3 or hidden.shape[0] != 1:
        raise ValueError('OPSD requires one unpadded sequence')
    if any(type(p) is not int or p < 0 or p >= hidden.shape[1] for p in positions):
        raise ValueError('causal hidden position out of bounds')
    return hidden[0, list(positions), :]


class OpsdTrainer:
    def __init__(self, model, *, hidden_fn=backbone_hidden, api=None, learning_rate=2e-5,
                 max_grad_norm=1.0, chunk_size=64, token_gate=False, gate_k=1.0):
        self.model, self.hidden_fn = model, hidden_fn
        self.api = api or prime_lora_api()
        adapters = checked_adapters(model, self.api)
        _head_weight(model)
        _settings(1., token_gate, gate_k)
        if type(chunk_size) is not int or chunk_size <= 0:
            raise ValueError('chunk_size must be a positive integer')
        for name, value in (('learning_rate', learning_rate), ('max_grad_norm', max_grad_norm)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(name + ' must be positive and finite')
        self.parameters = [p for m in adapters for p in [*m.lora_A, *m.lora_B] if p.requires_grad]
        if not self.parameters:
            raise ValueError('no trainable LoRA parameters')
        self.optimizer = torch.optim.AdamW(self.parameters, lr=learning_rate, weight_decay=0.)
        self.max_grad_norm = max_grad_norm
        self.chunk_size, self.token_gate, self.gate_k = chunk_size, token_gate, gate_k

    def step(self, samples):
        samples = tuple(samples)
        count = sum(len(s.target_ids) for s in samples)
        if count == 0:
            return dict(loss=0., assistant_tokens=0, gradient_norm=0., updated=False)
        with FORWARD_LOCK:
            checked_adapters(self.model, self.api)
            weight = _head_weight(self.model)
            device = weight.device
            self.optimizer.zero_grad(set_to_none=True)
            initial_counts = self.api.base.get_lora_num_tokens().clone()
            loss_value = 0.
            try:
                for sample in samples:
                    if not sample.target_ids:
                        continue
                    ids = torch.tensor([sample.student_ids], device=device, dtype=torch.long)
                    pos = torch.arange(ids.shape[1], device=device)[None, :]
                    self.api.base.set_lora_num_tokens(torch.full_like(initial_counts, ids.shape[1]))
                    student = _selected_hidden(self.hidden_fn(self.model, ids, pos), sample.student_positions)
                    teacher_ids = torch.tensor([sample.teacher_ids], device=device, dtype=torch.long)
                    teacher_pos = torch.arange(teacher_ids.shape[1], device=device)[None, :]
                    with frozen_teacher(self.model, teacher_ids.shape[1], api=self.api):
                        teacher = _selected_hidden(self.hidden_fn(self.model, teacher_ids, teacher_pos),
                                                    sample.teacher_positions).detach()
                    targets = torch.tensor(sample.target_ids, device=device, dtype=torch.long)
                    mask = torch.ones(targets.shape, device=device, dtype=torch.bool)
                    loss = chunked_jsd_loss(student, teacher, weight, mask, target_ids=targets,
                        chunk_size=self.chunk_size, temperature=sample.temperature,
                        token_gate=self.token_gate, gate_k=self.gate_k) * (targets.numel() / count)
                    if not torch.isfinite(loss):
                        raise ValueError('nonfinite OPSD loss')
                    loss.backward()
                    loss_value += float(loss.detach())
                norm = torch.nn.utils.clip_grad_norm_(self.parameters, self.max_grad_norm, error_if_nonfinite=True)
                self.optimizer.step()
            except BaseException:
                self.optimizer.zero_grad(set_to_none=True)
                raise
            finally:
                self.api.base.set_lora_num_tokens(initial_counts)
            return dict(loss=loss_value, assistant_tokens=count, gradient_norm=float(norm), updated=True)
