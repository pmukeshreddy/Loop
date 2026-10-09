"""No-network validation of the fixed dev pool, pins, thresholds and clients."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from pydantic import ValidationError
import yaml

from rlm_opsd.detectors import DetectorConfig
from rlm_opsd.harness.config import HarnessConfig
from rlm_opsd.prompts import PromptBuilder, PromptConfig
from rlm_opsd.prompts.templates import checked_text
from rlm_opsd.tasks.build import load_tasks
from rlm_opsd.tasks.models import FAMILIES
from .config import GateConfig


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_error(exc):
    # Pydantic's default formatting includes input values, potentially secrets.
    if isinstance(exc,ValidationError):
        return '; '.join('.'.join(map(str,e['loc']))+': '+e['msg'] for e in exc.errors(include_input=False,include_url=False))
    return str(exc)


@dataclass
class GatePlan:
    inputs: list
    harness_config: HarnessConfig
    prompt_config: PromptConfig
    detector_config: DetectorConfig
    prompt_builder: PromptBuilder
    provenance: dict


def prepare_gate(config):
    harness=HarnessConfig.from_yaml(config.harness_config)
    prompts=PromptConfig.from_yaml(config.prompt_config)
    detectors=DetectorConfig.from_yaml(config.detector_config)
    builder=PromptBuilder.load()
    if (config.base_model,config.revision)!=(prompts.model_name,prompts.revision):
        raise ValueError('base model/revision differs from pinned prompt configuration')
    checked_text(prompts.template_path,prompts.template_sha256)
    for endpoint in (config.root_endpoint,config.frozen_endpoint):
        if endpoint.api_key_var and not os.environ.get(endpoint.api_key_var):
            raise ValueError(f'missing API-key environment variable: {endpoint.api_key_var}')
    report_path=config.manifest_path.parent/'build-report.json'
    report=json.loads(report_path.read_text())
    if report.get('decontamination',{}).get('coverage_complete') is not True:
        raise ValueError('heldout coverage is incomplete; dev_behavior pool is inspection-only')
    inputs=list(load_tasks(config.manifest_path,split='dev_behavior'))
    if not inputs:
        raise ValueError('dev_behavior split is empty')
    manifest_rows=[json.loads(line) for line in config.manifest_path.read_text().splitlines()]
    by_id={r['task_id']:r for r in manifest_rows}
    actual=set()
    for example in inputs:
        info=example['info'];row=by_id[info['task_id']]
        bucket=row.get('knobs',{}).get('target_chars')
        if type(bucket) is not int or bucket<=0:
            raise ValueError('dev task needs an explicit positive target_chars size bucket')
        info['size_bucket']=bucket
        actual.add((info['family'],bucket))
        if info['task_id'] not in detectors.max_subcalls_expected and info['family'] not in detectors.max_subcalls_expected:
            raise ValueError(f'missing detector call limit for family {info["family"]}')
    expected={(r['family'],r['bucket']) for r in report.get('generated_grid',[]) if r['split']=='dev_behavior'}
    if not expected or actual!=expected or {f for f,_ in actual}!=set(FAMILIES):
        raise ValueError('dev_behavior family/size grid is missing, incomplete or inconsistent')
    provenance=dict(manifest_sha256=sha256(config.manifest_path),build_report_sha256=sha256(report_path),
        harness_config_sha256=sha256(config.harness_config),prompt_config_sha256=sha256(config.prompt_config),
        detector_config_sha256=sha256(config.detector_config),template_sha256=prompts.template_sha256,
        manual_version=builder.manual_version,base_model=config.base_model,revision=config.revision,
        enable_thinking=prompts.enable_thinking,
        endpoint_identity='operator-declared base weights; remote weight/template bytes not independently verified',
        dev_task_ids=[r['info']['task_id'] for r in inputs],
        grid=[dict(family=f,size_bucket=b) for f,b in sorted(actual)])
    return GatePlan(inputs,harness,prompts,detectors,builder,provenance)


def check_readiness(path):
    path=Path(path).resolve()
    blockers=[]
    try:
        raw=yaml.safe_load(path.read_text())
        if not isinstance(raw,dict): raise ValueError('gate config must be a mapping')
    except (OSError,ValueError,yaml.YAMLError) as exc:
        return dict(status='not_run',blockers=[safe_error(exc)],model_requests_sent=False)
    config=None
    try:
        config=GateConfig.from_yaml(path)
    except (ValueError,OSError) as exc:
        blockers.append('gate settings: '+safe_error(exc))
    try:
        detector_path=(path.parent/raw['detector_config']).resolve()
        DetectorConfig.from_yaml(detector_path)
    except (ValueError,OSError,KeyError,TypeError,yaml.YAMLError) as exc:
        blockers.append('detector settings: '+safe_error(exc))
    try:
        manifest=(path.parent/raw['manifest_path']).resolve()
        report=json.loads((manifest.parent/'build-report.json').read_text())
        if report.get('decontamination',{}).get('coverage_complete') is not True:
            blockers.append('heldout coverage incomplete; dev_behavior is inspection-only')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        blockers.append('task pool: '+safe_error(exc))
    if config is not None:
        try: prepare_gate(config)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            message='preflight: '+safe_error(exc)
            if message not in blockers: blockers.append(message)
    return dict(status='not_run' if blockers else 'ready',blockers=blockers,model_requests_sent=False)
