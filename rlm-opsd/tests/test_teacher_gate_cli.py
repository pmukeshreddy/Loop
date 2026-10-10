"""CLI contract checks; fixture execution is covered by teacher-gate HTTP tests."""
import json
from pathlib import Path
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_cli_check_reports_not_run_and_all_prerequisites_without_outputs(tmp_path,capsys):
    from rlm_opsd.eval.__main__ import main
    out=tmp_path/'must-not-exist'
    assert main(['teacher-gate','--config',str(ROOT/'configs/gate.yaml'),'--output',str(out),'--check'])==2
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='not_run' and not result['model_requests_sent']
    assert len(result['blockers'])>=3
    assert not out.exists()


def test_cli_run_refuses_unconfigured_gate_without_fake_report(tmp_path,capsys):
    from rlm_opsd.eval.__main__ import main
    out=tmp_path/'must-not-exist'
    assert main(['teacher-gate','--config',str(ROOT/'configs/gate.yaml'),'--output',str(out)])==2
    assert json.loads(capsys.readouterr().out)['status']=='not_run'
    assert not out.exists()


def test_make_target_and_module_help_are_runnable():
    command=subprocess.run(['make','-n','teacher-gate'],cwd=ROOT,capture_output=True,text=True)
    assert command.returncode==0
    assert '-m rlm_opsd.eval teacher-gate' in command.stdout
    help_run=subprocess.run([str(ROOT/'.venv/bin/python'),'-m','rlm_opsd.eval','teacher-gate','--help'],cwd=ROOT,capture_output=True,text=True)
    assert help_run.returncode==0
    assert '--config' in help_run.stdout and '--check' in help_run.stdout


def test_cli_requires_an_output_for_a_run_and_rejects_later_milestones():
    from rlm_opsd.eval.__main__ import main
    with pytest.raises(SystemExit):main(['teacher-gate','--config','configs/gate.yaml'])
    with pytest.raises(SystemExit):main(['opsd'])
