"""A narrow, source-checked overlay for Prime-RL's loss denominator.

The pinned trainer always divides by actual assistant-token count. Its public
custom-loss hook cannot change that denominator. Everything else uses public
custom advantage/loss hooks and the unchanged native training lifecycle.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PIN = "09e11c7527a242b9f150c7c4c71b1b96da66cb75"
LOSS_PATH = "rlm_grpo.objective.clipped_policy_loss"


def prepare_source(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise ValueError(f"GRPO requires Prime-RL {PIN}")
    # GRPO owns a pristine checkout; OPSD's distillation patch is not a dependency.
    dirty = subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=normal"],
        text=True)
    if dirty:
        raise ValueError("GRPO requires a pristine Prime-RL checkout; use rlm-grpo/.deps/prime-rl")
    relative = Path("src/prime_rl/trainer/rl/train.py")
    original = (source / relative).read_text()
    anchor = "        loss_scale = max(loss_scale, 1)\n"
    if original.count(anchor) != 1:
        raise ValueError("Prime-RL normalization source contract changed")
    insertion = (
        '        if getattr(config.loss, "import_path", None) == "' + LOSS_PATH + '":\n'
        '            from rlm_grpo.objective import loss_normalizer\n'
        '            loss_scale = loss_normalizer(\n'
        '                micro_batches, parallel_dims, config.loss.kwargs["max_context_tokens"])\n')
    patched = original.replace(anchor, anchor + insertion)
    target = output / "prime-grpo-runtime"
    # The original .deps checkout and installed distributions remain untouched.
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "src", target / "src", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    configs = "packages/prime-rl-configs/src"
    shutil.copytree(source / configs, target / configs, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (target / relative).write_text(patched)
    (target / "overlay.json").write_text(json.dumps(dict(commit=PIN, file=str(relative),
        before=hashlib.sha256(original.encode()).hexdigest(),
        after=hashlib.sha256(patched.encode()).hexdigest()), indent=2) + "\n")
    return [str(target / "src"), str(target / configs)]
