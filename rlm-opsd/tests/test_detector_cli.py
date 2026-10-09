"""Run the real offline CLI on explicit, hand-labelled fixture files."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


FIXTURES = Path(__file__).parent / "fixtures" / "detectors"
LABEL = "Hand-labelled fixtures; not model results"


def fixture_inputs(tmp_path):
    destination = tmp_path / "inputs with spaces"
    shutil.copytree(FIXTURES, destination)
    return destination


def run_cli(inputs, output, *extra, manifest="manifest.json", config="fixture-config.yaml"):
    return subprocess.run([sys.executable, "-m", "rlm_opsd.detectors", "--config", str(inputs / config),
                           "--manifest", str(inputs / manifest), "--output", str(output),
                           "--source-label", LABEL, *extra], capture_output=True, text=True, timeout=20)


def row(rows, metric, phase):
    matches = [item for item in rows if item["metric"] == metric and item["phase"] == phase
               and item["dimension"] == "overall" and not item["category"]]
    assert len(matches) == 1
    return matches[0]


def test_cli_resolves_relative_manifest_paths_and_writes_fixture_only_comparison(tmp_path):
    inputs = fixture_inputs(tmp_path)
    original = {path.name: path.read_bytes() for path in inputs.iterdir() if path.is_file()}
    output = tmp_path / "fixture report"
    result = run_cli(inputs, output)
    assert result.returncode == 0, result.stderr
    paths = json.loads(result.stdout)
    assert paths == {"markdown": str(output / "behavior.md"), "csv": str(output / "behavior.csv")}
    with (output / "behavior.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert row(rows, "D1", "before")["value"] == "0.0"
    assert row(rows, "D1", "teacher")["value"] == "1.0"
    assert row(rows, "D18", "teacher")["value"] == "0.1"
    assert row(rows, "task_success", "before")["value"] == "0.0"
    assert row(rows, "task_success", "teacher")["value"] == ""
    assert row(rows, "D1", "after")["status"] == "not run"
    assert json.loads(row(rows, "D1", "before")["trajectory_paths"]) == [str((inputs / "before.json").resolve())]
    assert LABEL in (output / "behavior.md").read_text()
    assert original == {path.name: path.read_bytes() for path in inputs.iterdir() if path.is_file()}


@pytest.mark.parametrize("missing", ["--config", "--manifest", "--output", "--source-label"])
def test_cli_requires_explicit_inputs_and_source_label(tmp_path, missing):
    inputs = fixture_inputs(tmp_path)
    flags = ["--config", str(inputs / "fixture-config.yaml"), "--manifest", str(inputs / "manifest.json"),
             "--output", str(tmp_path / "reports"), "--source-label", LABEL]
    index = flags.index(missing)
    del flags[index:index + 2]
    result = subprocess.run([sys.executable, "-m", "rlm_opsd.detectors", *flags],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert missing in result.stderr and "required" in result.stderr
    assert not (tmp_path / "reports").exists()


@pytest.mark.parametrize("manifest,error", [
    ({"records": []}, "list"),
    ([None], "record"),
    ([{"phase": "before"}], "trajectory_path"),
    ([{"phase": "unknown", "trajectory_path": "before.json"}], "phase"),
    ([{"phase": "before", "trajectory_path": "before.json", "task_success": 0}], "task_success"),
    ([{"phase": "before", "trajectory_path": "before.json", "task_metadata": []}], "task_metadata"),
    ([{"phase": "before", "trajectory_path": "before.json", "task_succes": True}], "task_succes"),
    ([{"phase": "before", "trajectory_path": "before.json"}] * 2, "duplicate"),
])
def test_cli_rejects_invalid_manifests_before_writing(tmp_path, manifest, error):
    inputs = fixture_inputs(tmp_path)
    (inputs / "bad.json").write_text(json.dumps(manifest))
    output = tmp_path / "reports"
    result = run_cli(inputs, output, manifest="bad.json")
    assert result.returncode == 1
    assert error in result.stderr and "Traceback" not in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("bad_file,error", [("manifest.json", "JSON"), ("before.json", "JSON"),
                                           ("fixture-config.yaml", "YAML")])
def test_cli_reports_parse_errors_without_partial_outputs(tmp_path, bad_file, error):
    inputs = fixture_inputs(tmp_path)
    (inputs / bad_file).write_text("{ this is: [ broken syntax")
    output = tmp_path / "reports"
    result = run_cli(inputs, output)
    assert result.returncode == 1
    assert error in result.stderr and "Traceback" not in result.stderr
    assert not output.exists()


def test_cli_does_not_fill_unset_operational_thresholds(tmp_path):
    inputs = fixture_inputs(tmp_path)
    (inputs / "fixture-config.yaml").write_text("probe_max_chars: null\n")
    result = run_cli(inputs, tmp_path / "reports")
    assert result.returncode == 1
    assert "probe_max_chars" in result.stderr
    assert not (tmp_path / "reports").exists()


def test_cli_missing_source_and_non_object_trace_are_errors(tmp_path):
    inputs = fixture_inputs(tmp_path)
    (inputs / "before.json").unlink()
    result = run_cli(inputs, tmp_path / "missing")
    assert result.returncode == 1 and "before.json" in result.stderr
    assert not (tmp_path / "missing").exists()
    (inputs / "before.json").write_text("[]")
    result = run_cli(inputs, tmp_path / "not-object")
    assert result.returncode == 1 and "object" in result.stderr
    assert not (tmp_path / "not-object").exists()


def test_cli_obeys_explicit_overwrite_without_touching_inputs(tmp_path):
    inputs = fixture_inputs(tmp_path)
    output = tmp_path / "reports"
    assert run_cli(inputs, output).returncode == 0
    content = (output / "behavior.md").read_bytes()
    refused = run_cli(inputs, output)
    assert refused.returncode == 1 and "exists" in refused.stderr
    assert (output / "behavior.md").read_bytes() == content
    replaced = run_cli(inputs, output, "--overwrite")
    assert replaced.returncode == 0, replaced.stderr
    assert (output / "behavior.md").read_bytes() == content


def test_cli_analysis_never_executes_trajectory_code(tmp_path):
    inputs = fixture_inputs(tmp_path)
    sentinel = tmp_path / "must-not-exist"
    trace_path = inputs / "before.json"
    trace = json.loads(trace_path.read_text())
    code = f"open({str(sentinel)!r}, 'w').write('unsafe')"
    trace["turns"][0]["code_blocks"] = [code]
    trace["turns"][0]["assistant_text"] = "```repl\n" + code + "\n```\nFINAL(done)"
    trace_path.write_text(json.dumps(trace))
    result = run_cli(inputs, tmp_path / "reports")
    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
