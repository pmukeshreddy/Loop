"""Final M6 artifact audit; no network, model execution or file mutation."""
import ast
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[3]
print('Command: Python immutable-input, links, syntax, whitespace, scope and evidence audit')
previous=(ROOT/'docs/logs/m5/23-artifact-audit.log').read_text()
for relative,expected in re.findall(r'(?:hash verified|dependency file) (.+?) ([0-9a-f]{64})',previous):
    actual=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    assert actual==expected,(relative,actual,expected)
    print('UNCHANGED',relative,actual)

docs=[ROOT/'docs'/name for name in ('OPSD_MODE_A.md','VERIFIED_APIS.md','PROGRESS.md')]
docs += [ROOT/'docs/logs/m6/24-review.md',ROOT/'docs/superpowers/plans/2026-10-09-m6.md']
links=0
for path in docs:
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
        if '://' in target or target.startswith('#'):continue
        target=unquote(target.split('#',1)[0])
        assert (path.parent/target).exists(),(path,target)
        links+=1
print('RELATIVE_LINKS_VERIFIED',links)

files=list((ROOT/'rlm_opsd/training').glob('*.py'))
files+=list((ROOT/'tests').glob('test_training_*.py'))+[ROOT/'tests/prime_cpu.py']
files+=list((ROOT/'docs/logs/m6').glob('*.py'))
for path in files:ast.parse(path.read_text(),filename=str(path))
for path in files+docs+[ROOT/'requirements-m6-local.txt']:
    assert path.read_text().endswith('\n'),path
    assert all(line==line.rstrip() for line in path.read_text().splitlines()),path
    print('ARTIFACT',path.relative_to(ROOT),hashlib.sha256(path.read_bytes()).hexdigest())

for line in (ROOT/'requirements-m6-local.txt').read_text().splitlines():
    if not line or line.startswith('#'):continue
    name,expected=line.split('==')
    assert version(name)==expected,(name,version(name))
    print('INSTALLED_PIN',name,expected)

assert '427 passed, 15 warnings' in (ROOT/'docs/logs/m6/21-full-suite.log').read_text()
assert '53 passed, 14 warnings' in (ROOT/'docs/logs/m6/20-m6-green.log').read_text()
for stage in ('small','27b'):
    assert not (ROOT/f'reports/opsd-a-{stage}').exists()
    for target in ('opsd-a','opsd-a-check'):
        data=(ROOT/f'docs/logs/m6/23-{stage}-{target}.log').read_text()
        assert '"status": "not_run"' in data and '"model_requests_sent": false' in data and 'exit_code=2' in data
assert not json.loads((ROOT/'data/build-report.json').read_text())['decontamination']['coverage_complete']
assert not (ROOT/'configs/opsd_mode_b.toml').exists()
assert not re.search(r'^opsd-b\s*:',(ROOT/'Makefile').read_text(),re.M)
assert not any('jsd' in path.stem or 'mode_b' in path.stem for path in (ROOT/'rlm_opsd/training').glob('*.py'))
print('SCOPE no M7 objective/target, no operational pretrained smoke reports, real coverage unchanged')

for command in (['git','diff','--check'],['git','status','--short'],
                ['git','-C','.deps/prime-rl','status','--short']):
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    print('COMMAND',json.dumps(command),'EXIT',result.returncode)
    print(result.stdout,end='')
    assert result.returncode==0,result.stderr
    if '-C' in command:assert not result.stdout
print('PASS: M6 artifacts verified. Required real pretrained smokes remain NOT RUN.')
