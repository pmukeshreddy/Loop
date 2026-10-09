import json
from pathlib import Path
import subprocess
import sys
import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('command,config',[('eval-behavior','eval.yaml'),('exit-check','exit.yaml')])
def test_m8_commands_fail_closed_with_unset_operator_inputs(tmp_path,command,config):
    process=subprocess.run([sys.executable,'-m','rlm_opsd.eval',command,'--config',str(ROOT/'configs'/config),
                            '--output',str(tmp_path/'run')],capture_output=True,text=True,cwd=ROOT)
    assert process.returncode==2,process.stderr
    result=json.loads(process.stdout)
    assert result['status']=='not_run' and result['model_requests_sent'] is False
    assert result['blockers'] and not (tmp_path/'run').exists()


@pytest.mark.parametrize('command',['eval-behavior','exit-check'])
def test_m8_make_targets_use_no_network_preflight(command):
    process=subprocess.run(['make',command+'-check',f'PYTHON={sys.executable}'],cwd=ROOT,capture_output=True,text=True)
    assert process.returncode==2
    assert '"status": "not_run"' in process.stdout and '"model_requests_sent": false' in process.stdout


def test_exit_settings_require_user_retention_path_and_both_tolerances():
    from rlm_opsd.eval.monitor_config import ExitConfig
    with pytest.raises(ValueError):ExitConfig.from_yaml(ROOT/'configs/exit.yaml')
    values=yaml.safe_load((ROOT/'configs/exit.yaml').read_text())
    assert values['retention_path'] is None
    assert values['rules']['behavior_tolerance'] is None
    assert values['rules']['retention_tolerance'] is None
