import argparse
import json
from pathlib import Path
import sys

import yaml

from .build import build_pool, verify_pool
from .decontam import HeldoutIndex
from .prepare import load_corpora, prepare_sources


def main():
    parser = argparse.ArgumentParser(description='M2 reproducible task generation and heldout decontamination')
    parser.add_argument('command', choices=['prepare', 'build', 'verify'])
    parser.add_argument('--config', default='configs/tasks.yaml')
    parser.add_argument('--output', default='data')
    parser.add_argument('--manifest', default='data/manifest.jsonl')
    args = parser.parse_args()
    try:
        config = yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))
        if args.command == 'prepare':
            result = prepare_sources(config)
        elif args.command == 'build':
            index = HeldoutIndex.load(config['heldout_index'])
            report = build_pool(config, args.output, corpora=load_corpora(config), heldout=index)
            result = dict(generated_total=report['generated_total'], written_total=report['written_total'],
                          verified_total=report['verified_total'], coverage_complete=report['decontamination']['coverage_complete'],
                          dropped_total=report['decontamination']['dropped_total'],
                          missing_benchmarks=report['decontamination']['missing_benchmarks'],
                          manifest=str(Path(args.output) / 'manifest.jsonl'), report=str(Path(args.output) / 'build-report.json'))
        else:
            result = dict(verified_total=verify_pool(args.manifest, corpora=load_corpora(config)))
        print(json.dumps(result, sort_keys=True))
    except (ValueError, KeyError, OSError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
