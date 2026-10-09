"""Read-only final M7 artifact audit; no model execution or network."""
import ast
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[3]
print('Command: M7 immutable-input, source, links, syntax, whitespace, scope and evidence audit')
previous=(ROOT/'docs/logs/m5/23-artifact-audit.log').read_text()
for relative,expected in re.findall(r'(?:hash verified|dependency file) (.+?) ([0-9a-f]{64})',previous):
    actual=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    assert actual==expected,(relative,actual,expected)
    print('UNCHANGED',relative,actual)

m6=(ROOT/'docs/logs/m6/25-artifact-audit.log').read_text()
preserved={'rlm_opsd/training/teacher.py','rlm_opsd/training/samples.py','rlm_opsd/training/mode_a.py',
           'tests/prime_cpu.py','tests/test_training_teacher.py','tests/test_training_samples.py',
           'requirements-m6-local.txt'}
for relative,expected in re.findall(r'ARTIFACT (.+?) ([0-9a-f]{64})',m6):
    if relative in preserved:
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,relative
        print('PRESERVED_M6',relative,expected)
        preserved.remove(relative)
assert not preserved,preserved

docs=[ROOT/'docs'/name for name in ('OPSD_MODE_A.md','OPSD_MODE_B.md','VERIFIED_APIS.md','PROGRESS.md')]
docs += [ROOT/'docs/logs/m7/19-review.md',ROOT/'docs/superpowers/plans/2026-10-09-m7.md']
links=0
for path in docs:
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
        if '://' in target or target.startswith('#'):continue
        target=unquote(target.split('#',1)[0])
        assert (path.parent/target).exists(),(path,target)
        links+=1
print('RELATIVE_LINKS_VERIFIED',links)

files=list((ROOT/'rlm_opsd/training').glob('*.py'))
files+=list((ROOT/'tests').glob('test_training_*.py'))
files+=list((ROOT/'docs/logs/m7').glob('*.py'))
for path in files:
    ast.parse(path.read_text(),filename=str(path))
    if path.name.startswith('test_'):
        assert not re.search(r'@pytest\.mark\.(skip|skipif|xfail)',path.read_text()),path
for path in files+docs+list((ROOT/'configs').glob('opsd_mode_b*.toml')):
    assert path.read_text().endswith('\n'),path
    assert all(line==line.rstrip() for line in path.read_text().splitlines()),path
    print('ARTIFACT',path.relative_to(ROOT),hashlib.sha256(path.read_bytes()).hexdigest())

for line in (ROOT/'requirements-m6-local.txt').read_text().splitlines():
    if not line or line.startswith('#'):continue
    name,expected=line.split('==')
    assert version(name)==expected,(name,version(name))
    print('UNCHANGED_INSTALLED_PIN',name,expected)

assert '501 passed, 15 warnings' in (ROOT/'docs/logs/m7/17-full-suite-final.log').read_text()
assert '74 passed, 14 warnings' in (ROOT/'docs/logs/m7/15-m7-final.log').read_text()
for stage in ('small','27b'):
    assert not (ROOT/f'reports/opsd-b-{stage}').exists()
    for target in ('opsd-b','opsd-b-check'):
        text=(ROOT/f'docs/logs/m7/18-{stage}-{target}.log').read_text()
        assert '"status": "not_run"' in text and '"model_requests_sent": false' in text and 'exit_code=2' in text
assert not json.loads((ROOT/'data/build-report.json').read_text())['decontamination']['coverage_complete']
makefile=(ROOT/'Makefile').read_text()
assert not re.search(r'^(eval-behavior|exit-check|grpo-smoke)\s*:',makefile,re.M)
assert not (ROOT/'configs/grpo.toml').exists()
print('SCOPE no M8/M9 targets, no real pretrained smoke reports, real coverage unchanged')

for command in (['git','diff','--check'],['git','status','--short'],
                ['git','-C','.deps/prime-rl','status','--short']):
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    print('COMMAND',json.dumps(command),'EXIT',result.returncode)
    print(result.stdout,end='')
    assert result.returncode==0,result.stderr
    if '-C' in command:assert not result.stdout
print('PASS: M7 artifacts verified. GPU/pretrained smokes remain NOT RUN.')
