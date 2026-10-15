import argparse
import asyncio
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Prime-RL GRPO after OPSD")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("train", "check"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=Path("configs/grpo.toml"))
        command.add_argument("--source", type=Path, default=Path(".deps/prime-rl"))
        command.add_argument("--max-steps", type=int)
    images = commands.add_parser("prepare-images")
    images.add_argument("--manifest", type=Path, required=True)
    merge = commands.add_parser("merge-checkpoint")
    merge.add_argument("--base", type=Path, required=True)
    merge.add_argument("--adapter", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "merge-checkpoint":
        from .checkpoint import merge_checkpoint
        merge_checkpoint(args.base, args.adapter, args.output)
        print(json.dumps(dict(checkpoint=str(args.output.resolve()))))
        return 0
    if args.command == "prepare-images":
        from .runtime import prepare_image
        from .tasks import load_pool

        async def prepare():
            seen = set()
            for task in load_pool(args.manifest):
                key = task.image or str(task.directory)
                if key not in seen:
                    image = await prepare_image(task)
                    print(json.dumps(dict(task_id=task.task_id, image=image)), flush=True)
                    seen.add(key)
        asyncio.run(prepare())
        return 0
    from .launch import launch
    return launch(args.config, args.source, check=args.command == "check", max_steps=args.max_steps)


if __name__ == "__main__":
    raise SystemExit(main())
