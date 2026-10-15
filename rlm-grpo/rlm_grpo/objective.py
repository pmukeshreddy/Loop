"""Native Prime-RL plugin hooks for sparse, group-relative repository rewards."""
import torch
import torch.distributed as dist

from prime_rl.orchestrator.advantage import AdvantageOutputs
from prime_rl.trainer.rl.loss import LossOutputs


def leave_one_out(inputs):
    """Compare submitted, non-truncated rollouts of the SAME task only.

    A_i = r_i - sum(r_j, j != i) / (n - 1). No reward-std scaling.
    One or zero eligible samples, all-pass, and all-fail groups yield zero.
    """
    advantages = []
    for group in inputs.rollouts:
        keys = {(r.get("env_name"), r["example_id"], r.get("info", {}).get("task_id")) for r in group}
        if len(keys) != 1:
            raise ValueError("GRPO group mixes different repository tasks")
        valid = [bool(r.get("info", {}).get("grpo_eligible")) for r in group]
        rewards = [float(r["reward"]) for r in group]
        if any(r not in {-1.0, 1.0} for r, keep in zip(rewards, valid) if keep):
            raise ValueError("Repository GRPO requires +1/-1 terminal rewards")
        count = sum(valid)
        total = sum(r for r, keep in zip(rewards, valid) if keep)
        advantages.append([r - (total - r) / (count - 1) if keep and count > 1 else 0.0
                           for r, keep in zip(rewards, valid)])
    return AdvantageOutputs(advantages=torch.tensor(advantages, dtype=torch.float32))


def clipped_policy_loss(inputs, *, clip_low=0.2, clip_high=0.28, max_context_tokens=32768):
    """Asymmetric PPO/GRPO surrogate, with no teacher KL or entropy term.

    The pinned trainer overlay supplies a constant context-capacity denominator
    via loss_normalizer. Do not divide by actual response length here.
    """
    if not 0 < clip_low < 1 or clip_high <= 0 or max_context_tokens <= 0:
        raise ValueError("Invalid GRPO loss configuration")
    mask = inputs.loss_mask.bool()
    current = inputs.trainer_logprobs[mask].float()
    old = inputs.inference_logprobs[mask].detach().float()
    advantage = inputs.advantages[mask].detach().float()
    # Operate only on model positions, so masked nonfinite observations cannot
    # produce NaN through a zero multiplier. Empty masks remain differentiable.
    ratio = (current - old).clamp(-30, 30).exp()
    clipped = ratio.clamp(1 - clip_low, 1 + clip_high)
    loss = -torch.minimum(ratio * advantage, clipped * advantage).sum()
    count = max(current.numel(), 1)
    return LossOutputs(loss=loss, metrics={
        "grpo_clip_fraction": ((ratio < 1 - clip_low) | (ratio > 1 + clip_high)).float().sum() / count,
        "grpo_ratio": ratio.detach().sum() / count,
    })


def loss_normalizer(micro_batches, parallel_dims, max_context_tokens):
    """Global active-sequence count times context cap; compensate FSDP averaging.

    Root and child token branches are native training sequences. Padding/dummy
    sequences have no trainable tokens and do not enter the denominator.
    """
    from prime_rl.trainer.utils import get_response_lengths

    if parallel_dims.cp != 1 or parallel_dims.pp != 1 or parallel_dims.ep != 1:
        raise ValueError("Repository GRPO normalization currently supports data parallelism only")
    local_count = 0
    for batch in micro_batches:
        lengths = get_response_lengths(batch["position_ids"])
        masks = batch["loss_mask"].reshape(-1).split(lengths)
        local_count += sum(int(mask.any().item()) for mask in masks)
    count = torch.tensor(float(local_count), device=torch.device("cuda", torch.cuda.current_device()))
    group = parallel_dims.get_mesh("dp").get_group()
    dist.all_reduce(count, group=group)
    world = dist.get_world_size(group)
    return max(float(count.item()), 1.0) * max_context_tokens / world
