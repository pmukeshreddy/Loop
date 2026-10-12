"""pytest plugin loaded into repository test processes: per-test outcomes as JSON.

This file is copied next to each run and imported by module name, so it must
not import the rest of rlm_opsd.
"""
import json
import os

_outcomes = {}


def _set(nodeid, outcome):
    # A later setup/teardown error overrides a passing call phase.
    if _outcomes.get(nodeid) in ('error', 'failed') and outcome in ('passed', 'skipped'):
        return
    _outcomes[nodeid] = outcome


def pytest_runtest_logreport(report):
    xfail = hasattr(report, 'wasxfail')
    if report.when == 'call':
        if report.passed:
            _set(report.nodeid, 'xpassed' if xfail else 'passed')
        elif report.failed:
            _set(report.nodeid, 'failed')
        else:
            _set(report.nodeid, 'xfailed' if xfail else 'skipped')
    elif report.failed:
        _set(report.nodeid, 'error')
    elif report.when == 'setup' and report.skipped:
        _set(report.nodeid, 'xfailed' if xfail else 'skipped')


def pytest_collectreport(report):
    if report.failed:
        _outcomes['collect::' + report.nodeid] = 'error'


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get('RLM_TASK_REPORT')
    if path:
        with open(path, 'w', encoding='utf-8') as stream:
            json.dump(dict(exitstatus=int(exitstatus), outcomes=_outcomes), stream, sort_keys=True)
