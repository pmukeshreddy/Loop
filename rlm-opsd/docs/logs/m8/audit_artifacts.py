"""Final M8 scope, preservation, syntax, documentation and evidence audit."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for line in (ROOT/'docs/logs/m7/20-artifact-audit.log').read_text().splitlines():
    parts=line.split()
    if len(parts)!=3:continue
    kind,relative,old=parts
    preserve=(kind in ('UNCHANGED','PRESERVED_M6') and relative not in ('AGENTS.md','docs/SPEC.md'))
    preserve |= kind=='ARTIFACT' and (relative.startswith('rlm_opsd/training/') or relative.startswith('tests/test_training')
        or relative.startswith('configs/opsd_'))
    if preserve:
        path=ROOT/relative;assert digest(path)==old,relative
        print('PRESERVED',relative,old)
paths=[*sorted((ROOT/'rlm_opsd/eval').glob('*.py')),*sorted((ROOT/'tests').glob('test_monitor*.py')),
       ROOT/'tests/test_exit_check.py',ROOT/'tests/test_retention.py']
for path in paths:ast.parse(path.read_text(),filename=str(path))
print('PYTHON_SYNTAX',len(paths),'files')
docs=[ROOT/'AGENTS.md',ROOT/'docs/SPEC.md',ROOT/'docs/MONITORING.md',ROOT/'docs/VERIFIED_APIS.md',
      ROOT/'docs/PROGRESS.md',ROOT/'docs/superpowers/plans/2026-10-09-m8.md',ROOT/'docs/logs/m8/28-review.md']
links=0
for path in docs:
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
        if '://' in target or target.startswith('#'):continue
        relative=target.split('#')[0]
        assert (path.parent/relative).exists(),(path,target)
        links+=1
print('RELATIVE_LINKS',links)
for path in [*paths,*docs,ROOT/'Makefile',ROOT/'configs/eval.yaml',ROOT/'configs/exit.yaml']:
    for n,line in enumerate(path.read_text().splitlines(),1):assert line.rstrip()==line,(path,n)
    print('ARTIFACT',path.relative_to(ROOT),digest(path))
from rlm_opsd.eval.monitor_config import MonitorConfig,ExitConfig,ExitRules
assert all('grpo' not in key for cls in (MonitorConfig,ExitConfig,ExitRules) for key in cls.model_fields)
assert 'retention_path' not in MonitorConfig.model_fields
assert ExitConfig.model_fields['retention_path'].is_required()
assert ExitRules.model_fields['behavior_tolerance'].is_required()
assert ExitRules.model_fields['retention_tolerance'].is_required()
settings=yaml.safe_load((ROOT/'configs/exit.yaml').read_text())
assert settings['retention_path'] is None
assert settings['rules']['behavior_tolerance'] is settings['rules']['retention_tolerance'] is None
assert not (ROOT/'configs/grpo.toml').exists()
assert not (ROOT/'reports/eval-behavior').exists() and not (ROOT/'reports/exit-check').exists()
for name in ('eval-behavior','eval-behavior-check','exit-check','exit-check-check'):
    log=(ROOT/f'docs/logs/m8/27-{name}.log').read_text()
    assert '"status": "not_run"' in log and '"model_requests_sent": false' in log
    print('NOT_RUN',name)
for repo in ('prime-rl','verifiers'):
    status=subprocess.check_output(['git','-C',str(ROOT/'.deps'/repo),'status','--porcelain'],text=True)
    assert not status,status
    print('PINNED_CHECKOUT_CLEAN',repo)
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
print('STATUS',subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).strip())
print('M8 ARTIFACT AUDIT PASS; no real model reports manufactured; M9 not implemented')
