"""Optional native sampled-token objective; no full-vocabulary divergence here."""
import math

import torch
from prime_rl.configs.trainer import DefaultLossConfig

from .teacher import FORWARD_LOCK, checked_adapters, prime_lora_api, selected_logits, teacher_logits


def sampled_loss(student,teacher,inference,*,teacher_tau=1.0,loss_api=None):
    if loss_api is None:
        from prime_rl.trainer.rl import loss as loss_api
    if student.ndim!=1 or teacher.shape!=student.shape or inference.shape!=student.shape:
        raise ValueError('sampled logprobs must be aligned one-dimensional tensors')
    if any(not torch.isfinite(t).all() for t in (student,teacher,inference)):
        raise ValueError('sampled logprobs must be finite')
    if not math.isfinite(teacher_tau) or teacher_tau<=0:
        raise ValueError('teacher_tau must be positive')
    inputs=loss_api.LossInputs(trainer_logprobs=student,teacher_logprobs=teacher.detach(),
        inference_logprobs=inference.detach(),advantages=torch.zeros_like(student),
        loss_mask=torch.ones_like(student,dtype=torch.bool))
    # Probability differences lie in [-1,1]: these bounds disable DPPO clipping.
    config=DefaultLossConfig(adv_tau=0.0,teacher_tau=teacher_tau,kl_tau=0.0,
                             dppo_mask_low=1.0,dppo_mask_high=1.0)
    return loss_api.default_loss_fn(inputs,config)


class ModeATrainer:
    """Synchronous correctness step using pinned prime-rl LoRA/forward/loss.

    All student/teacher forwards and backward share the process-global lock.
    This M6 runner has one dense adapter, no packing, FSDP, compile or CP.
    """
    def __init__(self,model,*,forward_fn,api=None,loss_api=None,learning_rate=2e-5,
                 teacher_tau=1.0,max_grad_norm=1.0):
        self.model,self.forward_fn=model,forward_fn
        self.api,self.loss_api=api or prime_lora_api(),loss_api
        adapters=checked_adapters(model,self.api)
        self.parameters=[p for m in adapters for p in [*m.lora_A,*m.lora_B] if p.requires_grad]
        if not self.parameters:raise ValueError('no trainable LoRA parameters')
        for name,value in [('learning_rate',learning_rate),('teacher_tau',teacher_tau),('max_grad_norm',max_grad_norm)]:
            if not math.isfinite(value) or value<=0:raise ValueError(name+' must be positive')
        self.teacher_tau,self.max_grad_norm=teacher_tau,max_grad_norm
        self.optimizer=torch.optim.AdamW(self.parameters,lr=learning_rate,weight_decay=0.0)

    def step(self,samples):
        count=sum(len(s.target_ids) for s in samples)
        if count==0:return dict(loss=0.0,assistant_tokens=0,gradient_norm=0.0,updated=False)
        with FORWARD_LOCK:
            checked_adapters(self.model,self.api)
            self.optimizer.zero_grad(set_to_none=True)
            device=next(self.model.parameters()).device
            initial_counts=self.api.base.get_lora_num_tokens().clone()
            loss_value=0.0
            try:
                for sample in samples:
                    if not sample.target_ids:continue
                    ids=torch.tensor([sample.student_ids],device=device,dtype=torch.long)
                    positions=torch.arange(ids.shape[1],device=device)[None,:]
                    self.api.base.set_lora_num_tokens(torch.full_like(initial_counts,ids.shape[1]))
                    student=selected_logits(self.forward_fn(self.model,ids,positions),sample.student_positions)
                    teacher=teacher_logits(self.model,sample,self.forward_fn,api=self.api)
                    targets=torch.tensor(sample.target_ids,device=device,dtype=torch.long)[:,None]
                    student_lp=(student/sample.temperature).log_softmax(-1).gather(1,targets).squeeze(1)
                    teacher_lp=(teacher/sample.temperature).log_softmax(-1).gather(1,targets).squeeze(1)
                    inference=torch.tensor(sample.inference_logprobs,device=device,dtype=torch.float32)
                    result=sampled_loss(student_lp,teacher_lp,inference,teacher_tau=self.teacher_tau,loss_api=self.loss_api)
                    loss=result.loss/count
                    if not torch.isfinite(loss):raise ValueError('nonfinite Mode A loss')
                    loss.backward()
                    loss_value+=float(loss.detach())
                norm=torch.nn.utils.clip_grad_norm_(self.parameters,self.max_grad_norm,error_if_nonfinite=True)
                self.optimizer.step()
            except BaseException:
                self.optimizer.zero_grad(set_to_none=True)
                raise
            finally:
                self.api.base.set_lora_num_tokens(initial_counts)
            return dict(loss=loss_value,assistant_tokens=count,gradient_norm=float(norm),updated=True)
