"""M5 CLI with explicit non-passing exit codes and a no-network preflight."""
import argparse
import asyncio
import json
from pathlib import Path

import yaml

from . import GateConfig, check_readiness, run_gate


EXIT_CODES={'passed':0,'completed':0,'not_due':0,'error':1,'not_run':2,'failed':3,'inconclusive':4}


def monitoring_command(args):
    from .monitor_config import MonitorConfig,ExitConfig
    from .monitor import check_monitor,run_monitor
    from .exit import check_exit,run_exit
    check=check_monitor if args.command=='eval-behavior' else check_exit
    if args.check:
        result=check(args.config)
        print(json.dumps(result,indent=2))
        return 0 if result['status']=='ready' else 2
    try:
        if args.command=='eval-behavior':
            result=asyncio.run(run_monitor(MonitorConfig.from_yaml(args.config),args.output))
        else:result=asyncio.run(run_exit(ExitConfig.from_yaml(args.config),args.output))
    except (ValueError,OSError,KeyError,TypeError,yaml.YAMLError) as exc:
        result=check(args.config) if not Path(args.output).exists() else dict(status='error',error_type=type(exc).__name__)
        if result['status']=='ready':result=dict(status='error',error_type=type(exc).__name__)
    print(json.dumps(result,indent=2))
    return EXIT_CODES.get(result['status'],1)


def main(argv=None):
    parser=argparse.ArgumentParser(description='M5 teacher gate using the pinned base model under x and y*')
    subparsers=parser.add_subparsers(dest='command',required=True)
    gate=subparsers.add_parser('teacher-gate')
    gate.add_argument('--config',default='configs/gate.yaml')
    gate.add_argument('--output',help='New output directory; existing runs are never overwritten')
    gate.add_argument('--check',action='store_true',help='Validate local prerequisites without sending model requests')
    for command,config in (('eval-behavior','configs/eval.yaml'),('exit-check','configs/exit.yaml')):
        sub=subparsers.add_parser(command)
        sub.add_argument('--config',default=config)
        sub.add_argument('--output',help='New output directory; never overwrite existing evidence')
        sub.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    if not args.check and not args.output:
        parser.error('--output is required for a run')
    if args.command!='teacher-gate':return monitoring_command(args)
    if args.check:
        result=check_readiness(args.config)
        print(json.dumps(result,indent=2))
        return 0 if result['status']=='ready' else 2
    try:
        config=GateConfig.from_yaml(args.config)
        result=asyncio.run(run_gate(config,args.output))
    except (ValueError,OSError,KeyError,TypeError,yaml.YAMLError) as exc:
        if not Path(args.output).exists():
            result=check_readiness(args.config)
            if result['status']=='ready':
                result=dict(status='error',error_type=type(exc).__name__)
        else:
            result=dict(status='error',error_type=type(exc).__name__,output=str(args.output))
        print(json.dumps(result,indent=2))
        return EXIT_CODES.get(result['status'],1)
    print(json.dumps(dict(status=result['status'],output=str(args.output),
                         planned_episodes=result['planned_episodes'],completed_episodes=result['completed_episodes']),indent=2))
    return EXIT_CODES[result['status']]


if __name__=='__main__':
    raise SystemExit(main())
