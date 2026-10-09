"""One-GPU prime-rl model/adapter setup for optional A or primary B smokes."""
from dataclasses import dataclass
from pathlib import Path
import sys


def require_cuda():
    import os
    import torch
    if sys.platform!='linux' or not torch.cuda.is_available():
        raise ValueError('Linux/CUDA runtime required; CPU fixtures are not pretrained smokes')
    if any(int(os.environ.get(key,default))!=int(default) for key,default in (
        ('WORLD_SIZE','1'),('LOCAL_WORLD_SIZE','1'),('RANK','0'),('LOCAL_RANK','0'))):
        raise ValueError('smoke requires one process/GPU; no FSDP, CP or compilation')
    if not torch.cuda.is_bf16_supported():raise ValueError('CUDA bfloat16 support required')


@dataclass
class Backend:
    model: object
    trainer: object
    kind: str='pretrained_model_smoke'

    def close(self):
        import torch.distributed as dist
        if dist.is_initialized():dist.destroy_process_group()


def configure_adapters(model, *, rank, alpha, api):
    import torch
    from .teacher import checked_adapters
    adapters=checked_adapters(model,api)
    for adapter in adapters:
        if any(torch.count_nonzero(p) for p in adapter.lora_B):
            raise ValueError('initial student must equal generation endpoint base: LoRA B must be zero')
    # Use the pinned ordinary matmul path on both Ampere and Hopper. The
    # grouped kernel selected automatically by rank/width has stricter hardware needs.
    for adapter in adapters:adapter.use_grouped_mm=False
    api.base.set_multilora_scaling(torch.full_like(api.base.get_multilora_scaling(),alpha/rank))


def create_trainer(config, model, *, api, mode_a_forward=None):
    common=dict(api=api,learning_rate=config.learning_rate,max_grad_norm=config.max_grad_norm)
    if config.mode=='b':
        from .mode_b import ModeBTrainer
        return ModeBTrainer(model,chunk_size=config.jsd_chunk_size,token_gate=config.token_gate,
                            gate_k=config.token_gate_k,**common)
    if config.mode=='a':
        from .mode_a import ModeATrainer
        if mode_a_forward is None:
            from prime_rl.trainer.model import forward as mode_a_forward
        return ModeATrainer(model,forward_fn=mode_a_forward,teacher_tau=config.teacher_tau,**common)
    raise ValueError('unsupported OPSD mode')


def load_backend(config,snapshot,output):
    require_cuda()
    import torch
    import torch.distributed as dist
    from prime_rl.configs.trainer import ModelConfig, LoRAConfig
    from prime_rl.trainer.model import get_model, forward
    from prime_rl.trainer.models.layers.lm_head import inject_prime_lm_head
    from prime_rl.trainer.lora import apply_lora_to_model
    from prime_rl.trainer.runs import setup_multi_run_manager
    from .teacher import prime_lora_api

    if dist.is_initialized():raise ValueError('smoke owns its process group; use a fresh process')
    torch.cuda.set_device(0)
    torch.manual_seed(config.seed)
    lora=LoRAConfig(rank=config.lora_rank,alpha=config.lora_alpha,dropout=0.0,
                   target_modules=['q_proj','k_proj','v_proj','o_proj'],modules_to_save=[])
    model_config=ModelConfig(name=str(snapshot),impl='hf',attn='eager',lora=lora,
        seq_len=config.max_seq_len,compile=None,ac=None,cp=1,ep=1,
        fused_lm_head_token_chunk_size='disabled')
    try:
        dist.init_process_group('nccl',init_method='file://'+str(Path(output).resolve()/'rendezvous'),rank=0,world_size=1)
        setup_multi_run_manager(Path(output),1,torch.device('cuda',0),lora)
        model=get_model(model_config,device=torch.device('cuda',0),dtype=torch.bfloat16)
        model=model.to('cuda:0')
        if config.mode=='a':inject_prime_lm_head(model,chunk_size=None)
        apply_lora_to_model(model,lora)
        api=prime_lora_api()
        configure_adapters(model,rank=lora.rank,alpha=lora.alpha,api=api)
        model.train()
        trainer=create_trainer(config,model,api=api,mode_a_forward=forward)
        return Backend(model,trainer)
    except BaseException:
        if dist.is_initialized():dist.destroy_process_group()
        raise
