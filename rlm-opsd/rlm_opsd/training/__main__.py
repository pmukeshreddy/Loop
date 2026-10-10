import argparse
import asyncio
import json

from .config import OpsdConfig
from .runner import check_readiness,run_smoke


def main(argv=None):
    parser=argparse.ArgumentParser(description='OPSD full-vocabulary JSD smoke; teacher scoring is local')
    parser.add_argument('command',choices=['smoke'])
    parser.add_argument('--config',default='configs/opsd.toml')
    parser.add_argument('--output')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    if not args.check and not args.output:parser.error('--output is required')
    try:config=OpsdConfig.from_toml(args.config)
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='not_run',error_type=type(exc).__name__,model_requests_sent=False)))
        return 2
    readiness=check_readiness(config)
    if args.check or readiness['status']!='ready':
        print(json.dumps(readiness,indent=2));return 0 if readiness['status']=='ready' else 2
    try:result=asyncio.run(run_smoke(config,args.output))
    except Exception as exc:result=dict(status='error',error_type=type(exc).__name__)
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
