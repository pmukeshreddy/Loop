"""Resolve the OPSD handoff and start Prime-RL's native asynchronous trainer."""
import json
import os
from pathlib import Path
import sys
import tomllib

from .checkpoint import checkpoint_files
from .prime import LOSS_PATH, prepare_source
from .tasks import load_pool

ROOT = Path(__file__).resolve().parents[2]


def resolve_config(path, *, max_steps=None):
    from prime_rl.configs.rl import RLConfig
    from rlm_opsd.prompts import PromptConfig
    from rlm_opsd.prompts.templates import checked_text

    path = Path(path).resolve(strict=True)
    values = tomllib.loads(path.read_text())
    handoff = values.pop("grpo")
    if set(handoff) != {"opsd_checkpoint", "manifest_path"}:
        raise ValueError("[grpo] requires opsd_checkpoint and manifest_path")
    checkpoint, _ = checkpoint_files(path.parent / handoff["opsd_checkpoint"])
    manifest = (path.parent / handoff["manifest_path"]).resolve(strict=True)
    tasks = load_pool(manifest)
    if {task.split for task in tasks} != {"train", "dev"}:
        raise ValueError("Provide both repository-disjoint train and dev tasks")
    if "name" in values.get("model", {}):
        raise ValueError("Set grpo.opsd_checkpoint; an independent base model.name is not allowed")
    values.setdefault("model", {})["name"] = str(checkpoint)
    values["output_dir"] = str((path.parent / values["output_dir"]).resolve())
    if max_steps is not None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        values["max_steps"] = max_steps
    config = RLConfig.model_validate(values)
    if config.clean_output_dir:
        raise ValueError("Use a new output directory or native checkpoint resume; auto-delete is disabled")
    if config.deployment.type != "single_node":
        raise ValueError("This Docker launcher currently requires single_node deployment")
    if getattr(config.trainer, "opsd", None) or getattr(config.orchestrator, "opsd", False):
        raise ValueError("OPSD distillation must be off in the GRPO phase")
    if config.orchestrator.teacher_model or config.orchestrator.teacher_rollout_model:
        raise ValueError("GRPO uses the shared OPSD-initialized policy, without a teacher")
    if config.trainer.model.cp != 1 or config.trainer.model.ep != 1:
        raise ValueError("GRPO normalization supports data parallelism with cp=ep=1")
    loss, advantage = config.trainer.loss, config.orchestrator.advantage
    if getattr(loss, "import_path", None) != LOSS_PATH:
        raise ValueError("Use the repository GRPO clipped loss plugin")
    if getattr(advantage, "import_path", None) != "rlm_opsd.grpo.objective.leave_one_out":
        raise ValueError("Use the submitted-only leave-one-out advantage plugin")
    limit = config.orchestrator.seq_len
    if limit != config.trainer.model.seq_len or loss.kwargs.get("max_context_tokens") != limit:
        raise ValueError("Trainer, rollout, and loss context limits must agree")
    if config.orchestrator.rollouts_per_example < 2:
        raise ValueError("GRPO requires at least two rollouts per task")
    if config.orchestrator.buffer.online_difficulty_filtering:
        raise ValueError("Native difficulty filtering assumes 0/1 rewards; keep it off for +1/-1")
    if config.inference is None or config.inference.model.max_model_len != limit:
        raise ValueError("Inference model context must match the GRPO sequence limit")
    if config.orchestrator.eval is None:
        raise ValueError("Configure periodic dev evaluation")
    config.output_dir = Path(values["output_dir"])
    config.trainer.output_dir = config.output_dir
    config.orchestrator.output_dir = config.output_dir / "run_default"
    config.orchestrator.use_renderer = False
    prompt = PromptConfig.from_yaml()
    checked_text(prompt.template_path, prompt.template_sha256)
    for tokenizer in (config.trainer.tokenizer, config.orchestrator.tokenizer):
        tokenizer.name = str(checkpoint)
        tokenizer.chat_template = str(prompt.template_path)
    config.inference.model.chat_template = str(prompt.template_path)
    for split, environments in (("train", config.orchestrator.train.env),
                                ("dev", config.orchestrator.eval.env)):
        if len(environments) != 1 or environments[0].id != "rlm_opsd.grpo.env":
            raise ValueError("Use one repository environment for train and one for dev")
        env = environments[0]
        for key in ("manifest_path", "split", "artifact_dir"):
            if key in env.args:
                raise ValueError(f"{key} is resolved by the GRPO launcher")
        env.args.update(manifest_path=str(manifest), split=split,
                        artifact_dir=str(config.output_dir / "trajectories" / split))
    # Re-validate exactly what the native launcher and its subprocesses read.
    return RLConfig.model_validate(config.model_dump(mode="json", exclude_none=True))


def launch(path, source, *, check=False, max_steps=None):
    path = Path(path).resolve(strict=True)
    raw = tomllib.loads(path.read_text())
    output = (path.parent / raw["output_dir"]).resolve()
    # Install only the narrow source overlay into this run directory before
    # importing native configs; subprocesses inherit the same PYTHONPATH.
    paths = prepare_source(source, output) + [str(ROOT)]
    sys.path[:0] = paths
    os.environ["PYTHONPATH"] = os.pathsep.join(paths + (
        [os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else []))
    config = resolve_config(path, max_steps=max_steps)
    import tomli_w

    launch_dir = config.output_dir / "grpo-launch"
    launch_dir.mkdir(parents=True, exist_ok=True)
    resolved = launch_dir / "rl.toml"
    resolved.write_text(tomli_w.dumps(config.model_dump(mode="json", exclude_none=True)))
    if check:
        print(json.dumps(dict(status="configured", config=str(resolved),
                              model_requests_sent=False, docker_runs=False, training="not run")))
        return 0
    from rlm_opsd.training.backend import require_cuda
    require_cuda()
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    os.execv(sys.executable, [sys.executable, "-m", "prime_rl.entrypoints.rl", "@", str(resolved)])

