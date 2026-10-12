import argparse
import asyncio
import json
from pathlib import Path
import sys

import yaml


def main():
    parser = argparse.ArgumentParser(description='AgentInstruct-style DeepSWE task generation for OPSD')
    parser.add_argument('command', choices=['prepare', 'generate', 'build', 'verify', 'status', 'reopen', 'repractice'])
    parser.add_argument('--config', default='configs/tasks.yaml')
    parser.add_argument('--output', default='data')
    parser.add_argument('--manifest', default='data/manifest.jsonl')
    parser.add_argument('--repos', nargs='*', help='limit generation to these repositories')
    parser.add_argument('--rounds', type=int, help='override max rounds per repository')
    parser.add_argument('--target', nargs=2, type=int, metavar=('TRAIN', 'DEV'), help='override accepted targets')
    parser.add_argument('--runs', type=int, default=1, help='verification runs per check (build: 0 skips release re-verification)')
    parser.add_argument('--codes', nargs='*', default=[], help='rejection codes to reopen after fixing their check')
    parser.add_argument('--focus', nargs='*', help='focused top-up: primary behaviors to generate; --target counts them')
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    root = config_path.parent.parent
    try:
        config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        if args.command == 'prepare':
            from .prepare import prepare_sources
            result = asyncio.run(prepare_sources(config, root, log=lambda m: print(m, file=sys.stderr)))
        elif args.command == 'generate':
            from .pipeline import Pipeline
            targets = dict(train=args.target[0], dev_behavior=args.target[1]) if args.target else None
            pipeline = Pipeline(config, config_dir=root, repos=args.repos, max_rounds=args.rounds, targets=targets,
                                focus=args.focus, log=lambda m: print(m, file=sys.stderr, flush=True))
            result = asyncio.run(pipeline.run())
        elif args.command == 'build':
            from .build import build_pool
            report = build_pool(config, root, args.output, verify_runs=args.runs)
            result = dict(accepted_total=report['accepted_total'], written_total=report['written_total'],
                          written_by_split=report['written_by_split'],
                          rejected_total=report['rejections']['total'],
                          reverification_failed=len(report['reverification']['failed']),
                          coverage_complete=report['decontamination']['coverage_complete'],
                          dropped_total=report['decontamination']['dropped_total'],
                          missing_benchmarks=report['decontamination']['missing_benchmarks'],
                          manifest=str(Path(args.output) / 'manifest.jsonl'))
        elif args.command == 'verify':
            from .reverify import verify_pool
            result = asyncio.run(verify_pool(config, root, args.manifest, runs=args.runs,
                                             log=lambda m: print(m, file=sys.stderr)))
            if result['failed']:
                print(json.dumps(result, sort_keys=True))
                return 1
        elif args.command == 'repractice':
            from .pipeline import repractice
            result = repractice(config, root)
        elif args.command == 'reopen':
            from .store import reopen
            result = dict(reopened=reopen(root / config['work_dir'], set(args.codes)))
        else:
            from .status import status
            result = status(config, root)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, KeyError, OSError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
