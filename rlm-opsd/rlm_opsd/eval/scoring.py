"""Local frozen-base KL(T||S) on recorded root targets."""
import torch
from torch.nn import functional as F

from rlm_opsd.training.opsd import backbone_hidden, _head_weight, _selected_hidden
from rlm_opsd.training.teacher import FORWARD_LOCK, checked_adapters, frozen_teacher, prime_lora_api
from .preflight import sha256


def load_adapter(model, path, checksum, *, api=None):
    """Load only a complete finite native MultiLoRA A/B state; validate before copy."""
    if sha256(path)!=checksum:raise ValueError('checkpoint hash differs')
    api=api or prime_lora_api()
    adapters=checked_adapters(model,api)
    allowed={id(p) for m in adapters for p in [*m.lora_A,*m.lora_B]}
    expected={n:p for n,p in model.named_parameters() if id(p) in allowed}
    state=torch.load(path,map_location='cpu',weights_only=True)
    if not isinstance(state,dict) or state.keys()!=expected.keys():
        raise ValueError('checkpoint must contain exactly all native adapter parameters')
    for name,value in state.items():
        if (not isinstance(value,torch.Tensor) or value.shape!=expected[name].shape
                or value.dtype!=expected[name].dtype or not torch.isfinite(value).all()):
            raise ValueError('checkpoint tensor shape, dtype or finite-value check failed')
    with FORWARD_LOCK,torch.no_grad():
        for name,value in state.items():expected[name].copy_(value)


def token_offsets(tokenizer, ids):
    """Offset lookup only: never supplies or replaces the scored rollout IDs.

    Decode all recorded completion tokens (including reasoning and specials),
    require an exact tokenizer round trip, and retain Unicode byte overlaps.
    Noncanonical token sequences fail closed instead of guessing offsets.
    """
    ids=list(ids)
    text=tokenizer.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    encoded=tokenizer(text,add_special_tokens=False,return_offsets_mapping=True)
    if list(encoded['input_ids'])!=ids:raise ValueError('completion tokens do not round-trip exactly for offsets')
    specials=set(tokenizer.all_special_ids)
    offsets=[(0,0) if token in specials else tuple(offset)
             for token,offset in zip(ids,encoded['offset_mapping'],strict=True)]
    return dict(text=text,token_ids=ids,offsets=offsets)


def score_samples(model, samples, *, chunk_size=64, api=None):
    if type(chunk_size) is not int or chunk_size<=0:raise ValueError('chunk_size must be positive')
    api=api or prime_lora_api()
    with FORWARD_LOCK,torch.no_grad():
        checked_adapters(model,api);weight=_head_weight(model);device=weight.device
        flags=[(m,m.training) for m in model.modules()]
        counts=api.base.get_lora_num_tokens().clone()
        results=[]
        try:
            model.eval()
            for sample in samples:
                if not sample.target_ids:
                    results.append(dict(kl=[]));continue
                ids=torch.tensor([sample.student_ids],device=device)
                pos=torch.arange(ids.shape[1],device=device)[None,:]
                api.base.set_lora_num_tokens(torch.full_like(counts,ids.shape[1]))
                student=_selected_hidden(backbone_hidden(model,ids,pos),sample.student_positions)
                ids=torch.tensor([sample.teacher_ids],device=device)
                pos=torch.arange(ids.shape[1],device=device)[None,:]
                with frozen_teacher(model,ids.shape[1],api=api):
                    teacher=_selected_hidden(backbone_hidden(model,ids,pos),sample.teacher_positions)
                if len(student)!=len(teacher) or len(student)!=len(sample.target_ids):
                    raise ValueError('unaligned monitoring hidden rows')
                kl=[]
                for start in range(0,len(student),chunk_size):
                    with torch.autocast(device_type=device.type,enabled=False):
                        s=F.linear(student[start:start+chunk_size],weight).float()/sample.temperature
                        t=F.linear(teacher[start:start+chunk_size],weight).float()/sample.temperature
                        s=s.log_softmax(-1);t=t.log_softmax(-1)
                        if not torch.isfinite(s).all() or not torch.isfinite(t).all():
                            raise ValueError('nonfinite monitoring log probabilities')
                        divergence=(t.exp()*(t-s)).sum(-1)
                        # Tiny negative roundoff is not negative mathematical KL.
                        if (divergence < -1e-5).any() or not torch.isfinite(divergence).all():
                            raise ValueError('invalid monitoring divergence')
                        kl.extend(divergence.clamp_min(0).cpu().tolist())
                results.append(dict(kl=kl))
        finally:
            api.base.set_lora_num_tokens(counts)
            for module,training in flags:module.training=training
        return results
