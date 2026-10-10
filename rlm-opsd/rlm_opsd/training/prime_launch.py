"""Preflight then launch prime-rl's native multi-step RL entry point."""
import argparse
import json
import os
from pathlib import Path
import sys
import tomllib

from .prime_patch import ROOT, apply_patch, source_paths


def load_launch_config(path):
    from prime_rl.configs.rl import RLConfig
    from .config import OpsdConfig

    path = Path(path).resolve()
    values = tomllib.loads(path.read_text())
    integration = values.pop('opsd')
    if set(integration) != {'smoke_config'}:
        raise ValueError('opsd settings must identify the existing pinned smoke/gate config')
    smoke = OpsdConfig.from_toml(path.parent / integration['smoke_config'])
    config = RLConfig.model_validate(values)
    if config.trainer.opsd is None:
        raise ValueError('opsd-train requires trainer.opsd')
    if config.model is None or config.model.name != smoke.base_model:
        raise ValueError('training model differs from pinned gate model')
    objective = config.trainer.opsd
    if (objective.temperature, objective.token_gate, objective.gate_k) != (
            smoke.temperature, smoke.token_gate, smoke.token_gate_k):
        raise ValueError('OPSD objective differs from small-model/gate configuration')
    if config.deployment.type != 'single_node':
        raise ValueError('this launcher requires single_node deployment with FSDP training GPUs')
    if config.clean_output_dir:
        raise ValueError('choose a new output directory or resume; automatic deletion is disabled')
    config.output_dir = (path.parent / config.output_dir).resolve()
    config.trainer.output_dir = config.output_dir
    config.orchestrator.output_dir = config.output_dir / 'run_default'
    return config, smoke


def prepare_config(config, smoke):
    from rlm_opsd.prompts import ChatRenderer, PromptBuilder, PromptConfig
    from rlm_opsd.tasks.build import load_tasks
    from .runner import verify_gate, verify_small_smoke, cached_snapshot

    gate, plan = verify_gate(smoke)
    verify_small_smoke(smoke)
    snapshot = cached_snapshot(smoke)
    prompt = PromptConfig.from_yaml(smoke.prompt_config)
    renderer = ChatRenderer(prompt)
    builder = PromptBuilder.load()
    tasks = list(load_tasks(gate.manifest_path, split='train'))
    if not tasks:
        raise ValueError('decontaminated train split is empty')
    for task in tasks:
        pair = builder.build(query=task['info']['query'], context=task['info']['context'], config=plan.harness_config)
        prefixes = renderer.prefixes(pair)
        if config.orchestrator.seq_len + len(prefixes.teacher_ids) - len(prefixes.student_ids) > config.trainer.model.seq_len:
            raise ValueError('trainer sequence limit must reserve space for the privileged teacher prefix')
    # The pin is a fully cached immutable snapshot path for every native process.
    config.model.name = str(snapshot)
    config.trainer.model.name = str(snapshot)
    config.orchestrator.model.name = str(snapshot)
    # Use the pinned server chat template and recorded response token IDs.
    config.orchestrator.use_renderer = False
    for tokenizer in (config.trainer.tokenizer, config.orchestrator.tokenizer):
        tokenizer.name = str(snapshot)
        tokenizer.chat_template = str(prompt.template_path)
    if config.inference is not None:
        config.inference.model.name = str(snapshot)
        config.inference.model.chat_template = str(prompt.template_path)
    for env in config.orchestrator.train.env:
        env.args = dict(manifest_path=str(gate.manifest_path), harness_config=str(gate.harness_config),
            prompt_config=str(smoke.prompt_config), frozen_model=gate.frozen_endpoint.served_model,
            frozen_client=dict(api_base_url=gate.frozen_endpoint.base_url,
                api_key_var=gate.frozen_endpoint.api_key_var or '', timeout=gate.request_timeout_s,
                max_retries=0), log_dir=str(config.output_dir / 'trajectories'))
    # The native launcher serializes and reloads these exact subconfigs.
    from prime_rl.configs.rl import RLConfig
    return RLConfig.model_validate(config.model_dump(mode='json', exclude_none=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/opsd_train.toml')
    parser.add_argument('--source', type=Path, default=ROOT / '.deps/prime-rl')
    parser.add_argument('--check', action='store_true', help='CPU-only validation; no model requests or GPU launch')
    args = parser.parse_args(argv)
    try:
        patch_state = apply_patch(args.source)
        paths = source_paths(args.source)
        sys.path[:0] = paths
        os.environ['PYTHONPATH'] = os.pathsep.join(paths + ([os.environ['PYTHONPATH']] if os.environ.get('PYTHONPATH') else []))
        config, smoke = load_launch_config(args.config)
        config = prepare_config(config, smoke)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps(dict(status='not_run', blocker=str(exc), model_requests_sent=False, gpu_results='not run')))
        return 2
    if args.check:
        print(json.dumps(dict(status='ready', patch=patch_state, model_requests_sent=False, gpu_results='not run')))
        return 0
    from .backend import require_cuda
    require_cuda()
    import tomli_w
    launch_dir = config.output_dir / 'opsd-launch'
    launch_dir.mkdir(parents=True, exist_ok=True)
    resolved = launch_dir / 'rl.toml'
    resolved.write_text(tomli_w.dumps(config.model_dump(mode='json', exclude_none=True)))
    # The native launcher resolves inference/torchrun/orchestrator from PATH.
    os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
    os.execv(sys.executable, [sys.executable, '-m', 'prime_rl.entrypoints.rl', '@', str(resolved)])


if __name__ == '__main__':
    raise SystemExit(main())
