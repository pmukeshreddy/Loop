"""Offline report contracts; every input below is a hand-labelled fixture.

The temporary files explicitly say they are fixtures, never model rollouts.
Expected rates and denominators are hand-calculated rather than recomputed
using the implementation's aggregators.
"""
import csv
import json
from pathlib import Path

import pytest


def fixture_record(tmp_path, name="one", phase="before", **updates):
    path = tmp_path / f"fixture-{name}.json"
    path.write_text(json.dumps({"fixture": True, "description": "Hand-labelled; not model results"}))
    analysis = {
        "task_id": name, "family": "sparse_retrieval", "domain": "long_context",
        "size_bucket": 8000, "tags": ["sparse"],
        "detectors": {**{f"D{i}": True for i in range(1, 16)}, "D16": 0.0,
                      "D17": True, "D18": 0.5, "D19": "regex_filter"},
        "task_tag_match": True,
        "counts": {"subcall_count": 1, "subcall_mean_prompt_chars": 100.0,
                   "subcall_max_prompt_chars": 100, "truncation_events": 0,
                   "syntax_error_blocks": 0, "code_blocks": 2},
        "coverage_lower_bound": 0.5, "unknown_reasons": {}, "facts": [],
    }
    analysis.update(updates)
    return {"phase": phase, "trajectory_path": path, "analysis": analysis}


def metric(rows, name, phase="before", dimension="overall", group="all", category=""):
    matches = [row for row in rows if (row["phase"], row["dimension"], row["group"],
               row["metric"], row["category"]) == (phase, dimension, group, name, category)]
    assert len(matches) == 1
    return matches[0]


def test_boolean_rates_exclude_unknown_evidence_and_keep_known_false(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    first, second, third = [fixture_record(tmp_path, name) for name in ("a", "b", "c")]
    second["analysis"]["detectors"]["D1"] = False
    third["analysis"]["detectors"]["D1"] = None
    third["analysis"]["task_tag_match"] = None
    rows = aggregate_behavior(iter([first, second, third]))
    row = metric(rows, "D1")
    assert (row["value"], row["numerator"], row["denominator"]) == (0.5, 1, 2)
    assert (row["known"], row["unknown"], row["trajectories"]) == (2, 1, 3)
    assert row["trajectory_paths"] == [str(item["trajectory_path"].resolve()) for item in (first, second, third)]
    assert metric(rows, "task_tag_match")["denominator"] == 2
    assert {f"D{i}" for i in range(1, 20)} <= {row["metric"] for row in rows}


def test_syntax_errors_pool_blocks_instead_of_averaging_trajectory_rates(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    first, second, unknown = [fixture_record(tmp_path, name) for name in ("a", "b", "c")]
    first["analysis"]["detectors"]["D16"] = 0.5
    first["analysis"]["counts"]["syntax_error_blocks"] = 1
    second["analysis"]["counts"]["code_blocks"] = 8
    unknown["analysis"]["detectors"]["D16"] = None
    unknown["analysis"]["counts"]["syntax_error_blocks"] = None
    row = metric(aggregate_behavior([first, second, unknown]), "D16")
    assert (row["value"], row["numerator"], row["denominator"]) == (0.1, 1, 10)
    assert (row["known"], row["unknown"]) == (2, 1)


def test_subcall_prompt_mean_is_weighted_by_actual_call_count(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    first, second, empty = [fixture_record(tmp_path, name) for name in ("a", "b", "empty")]
    second["analysis"]["counts"].update(subcall_count=3, subcall_mean_prompt_chars=300.0,
                                       subcall_max_prompt_chars=500, truncation_events=2)
    empty["analysis"]["counts"].update(subcall_count=0, subcall_mean_prompt_chars=0,
                                      subcall_max_prompt_chars=0)
    rows = aggregate_behavior([first, second, empty])
    mean = metric(rows, "subcall_mean_prompt_chars")
    assert (mean["value"], mean["numerator"], mean["denominator"]) == (250.0, 1000.0, 4)
    assert metric(rows, "subcall_count")["value"] == 4
    assert metric(rows, "subcall_mean_count")["value"] == pytest.approx(4 / 3)
    assert metric(rows, "subcall_max_prompt_chars")["value"] == 500
    assert metric(rows, "truncation_events")["value"] == 2


def test_coverage_and_first_decomposition_distributions_use_known_samples(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    first, second, third = [fixture_record(tmp_path, name) for name in ("a", "b", "c")]
    second["analysis"]["detectors"].update(D18=1.0, D19="direct_read")
    third["analysis"]["detectors"].update(D18=None, D19=None)
    third["analysis"]["coverage_lower_bound"] = 0.0
    rows = aggregate_behavior([first, second, third])
    coverage = metric(rows, "D18")
    assert (coverage["value"], coverage["denominator"], coverage["unknown"]) == (0.75, 2, 1)
    assert metric(rows, "coverage_lower_bound")["value"] == pytest.approx(1 / 3)
    regex = metric(rows, "D19", category="regex_filter")
    assert (regex["value"], regex["numerator"], regex["denominator"], regex["unknown"]) == (0.5, 1, 2, 1)
    assert metric(rows, "D19", category="chunk_subcall")["value"] == 0.0


def test_task_success_is_only_computed_for_explicitly_supplied_labels(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    records = [fixture_record(tmp_path, name) for name in ("yes", "no", "missing")]
    assert metric(aggregate_behavior(records), "task_success")["value"] is None
    records[0]["task_success"], records[1]["task_success"] = True, False
    row = metric(aggregate_behavior(records), "task_success")
    assert (row["value"], row["known"], row["unknown"], row["denominator"]) == (0.5, 2, 1, 2)


def test_absent_phases_and_groups_are_not_run_rather_than_measured_zero(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    before = fixture_record(tmp_path, "before")
    teacher = fixture_record(tmp_path, "teacher", "teacher", family="repo_qa", domain="code", size_bucket=None)
    teacher["analysis"]["detectors"]["D1"] = False
    rows = aggregate_behavior([before, teacher])
    assert metric(rows, "D1", "teacher")["value"] == 0.0
    absent = metric(rows, "D1", "after")
    assert (absent["status"], absent["value"], absent["trajectory_paths"]) == ("not run", None, [])
    assert absent["numerator"] is None and absent["denominator"] is None
    missing_group = metric(rows, "D1", "before", "family", "repo_qa")
    assert missing_group["status"] == "not run"
    assert metric(rows, "D1", "teacher", "size_bucket", "unknown")["value"] == 0
    assert metric(rows, "D1", "before", "size_bucket", "8000")["value"] == 1
    assert metric(rows, "D1", "teacher", "domain", "code")["value"] == 0


def test_empty_input_and_zero_block_or_subcall_counts_are_not_nan(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    empty_rows = aggregate_behavior([])
    assert {row["phase"] for row in empty_rows} == {"before", "teacher", "after"}
    assert all(row["status"] == "not run" and row["value"] is None for row in empty_rows)
    record = fixture_record(tmp_path)
    record["analysis"]["counts"].update(code_blocks=0, syntax_error_blocks=0,
                                       subcall_count=0, subcall_mean_prompt_chars=0,
                                       subcall_max_prompt_chars=0)
    rows = aggregate_behavior([record])
    assert metric(rows, "D16")["value"] is None
    assert metric(rows, "subcall_mean_prompt_chars")["value"] is None
    assert metric(rows, "subcall_max_prompt_chars")["value"] is None
    assert metric(rows, "subcall_count")["value"] == 0
    json.dumps(rows, allow_nan=False)


def test_written_markdown_and_csv_link_each_metric_to_source_files(tmp_path):
    from rlm_opsd.detectors.reports import write_behavior_report

    before = fixture_record(tmp_path, "with space(1)", family="repo|qa\n<label>")
    destination = tmp_path / "reports" / "fixture-only"
    paths = write_behavior_report([before], destination,
                                  source_label="Hand-labelled fixtures; not model results")
    assert paths == {"markdown": destination / "behavior.md", "csv": destination / "behavior.csv"}
    text = paths["markdown"].read_text()
    assert "Hand-labelled fixtures; not model results" in text
    assert "not run" in text
    assert "fixture-with%20space%281%29.json" in text
    assert "repo\\|qa" in text and "&lt;label&gt;" in text
    assert "[logs](#sources-" in text
    with paths["csv"].open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = metric(rows, "D1")
    assert row["value"] == "1.0"
    assert json.loads(row["trajectory_paths"]) == [str(before["trajectory_path"].resolve())]
    assert metric(rows, "D1", "after")["value"] == ""


@pytest.mark.parametrize("phase", ["baseline", "", None, 0])
def test_invalid_phases_are_rejected(tmp_path, phase):
    from rlm_opsd.detectors.reports import aggregate_behavior

    with pytest.raises(ValueError, match="phase"):
        aggregate_behavior([fixture_record(tmp_path, phase=phase)])


def test_duplicate_paths_are_rejected_even_under_another_phase_or_symlink(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    alias = tmp_path / "alias.json"
    alias.symlink_to(record["trajectory_path"])
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_behavior([record, {**record, "phase": "teacher", "trajectory_path": alias}])


@pytest.mark.parametrize("key,value", [("D1", 1), ("D16", float("nan")), ("D18", float("inf")),
                                      ("D18", -0.1), ("D18", 1.1), ("D19", "invented")])
def test_invalid_detector_values_are_rejected(tmp_path, key, value):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    record["analysis"]["detectors"][key] = value
    with pytest.raises(ValueError, match=key):
        aggregate_behavior([record])


@pytest.mark.parametrize("key,value", [("subcall_count", -1), ("subcall_count", True),
    ("subcall_count", 1.5), ("subcall_mean_prompt_chars", float("nan")),
    ("syntax_error_blocks", 3), ("subcall_max_prompt_chars", 50)])
def test_invalid_or_inconsistent_counts_are_rejected(tmp_path, key, value):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    record["analysis"]["counts"][key] = value
    with pytest.raises(ValueError):
        aggregate_behavior([record])


def test_inconsistent_syntax_error_rate_is_rejected(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    record["analysis"]["detectors"]["D16"] = 0.5
    with pytest.raises(ValueError, match="D16"):
        aggregate_behavior([record])


@pytest.mark.parametrize("success", [0, "true", None])
def test_present_task_success_must_be_boolean(tmp_path, success):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    record["task_success"] = success
    with pytest.raises(ValueError, match="task_success"):
        aggregate_behavior([record])


def test_missing_source_or_schema_is_rejected_before_writing(tmp_path):
    from rlm_opsd.detectors.reports import write_behavior_report

    record = fixture_record(tmp_path)
    record["trajectory_path"].unlink()
    destination = tmp_path / "reports"
    with pytest.raises(ValueError, match="trajectory_path"):
        write_behavior_report([record], destination)
    assert not destination.exists()
    record = fixture_record(tmp_path)
    del record["analysis"]["detectors"]["D2"]
    with pytest.raises(ValueError, match="D2"):
        write_behavior_report([record], destination)
    assert not destination.exists()


def test_write_refuses_unrelated_files_without_partial_output(tmp_path):
    from rlm_opsd.detectors.reports import write_behavior_report

    record = fixture_record(tmp_path)
    destination = tmp_path / "reports"
    destination.mkdir()
    existing = destination / "behavior.csv"
    existing.write_text("unrelated content")
    with pytest.raises(FileExistsError):
        write_behavior_report([record], destination)
    assert existing.read_text() == "unrelated content"
    assert not (destination / "behavior.md").exists()
    with pytest.raises(FileExistsError):
        write_behavior_report([record], destination, overwrite=True)
    assert existing.read_text() == "unrelated content"


def test_overwrite_only_replaces_own_report_and_preserves_other_files(tmp_path):
    from rlm_opsd.detectors.reports import write_behavior_report

    record = fixture_record(tmp_path)
    destination = tmp_path / "reports"
    paths = write_behavior_report([record], destination)
    unrelated = destination / "notes.txt"
    unrelated.write_text("keep this")
    with pytest.raises(FileExistsError):
        write_behavior_report([record], destination)
    record["analysis"]["detectors"]["D1"] = False
    write_behavior_report([record], destination, overwrite=True)
    with paths["csv"].open(newline="") as handle:
        assert metric(list(csv.DictReader(handle)), "D1")["value"] == "0.0"
    assert unrelated.read_text() == "keep this"


def test_writer_never_overwrites_a_source_trajectory_or_output_symlink(tmp_path):
    from rlm_opsd.detectors.reports import write_behavior_report

    record = fixture_record(tmp_path)
    destination = tmp_path / "reports"
    destination.mkdir()
    (destination / "behavior.md").symlink_to(record["trajectory_path"])
    with pytest.raises(FileExistsError):
        write_behavior_report([record], destination, overwrite=True)
    assert json.loads(record["trajectory_path"].read_text())["fixture"] is True


def test_inconsistent_prompt_maximum_is_rejected(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    record["analysis"]["counts"]["subcall_max_prompt_chars"] = 200
    with pytest.raises(ValueError, match="subcall"):
        aggregate_behavior([record])


def test_coverage_lower_bound_above_exact_coverage_is_rejected(tmp_path):
    from rlm_opsd.detectors.reports import aggregate_behavior

    record = fixture_record(tmp_path)
    record["analysis"]["coverage_lower_bound"] = 0.9
    with pytest.raises(ValueError, match="coverage_lower_bound"):
        aggregate_behavior([record])


def test_overwrite_rejects_binary_unrelated_files_with_no_changes(tmp_path):
    from rlm_opsd.detectors.reports import write_behavior_report

    record = fixture_record(tmp_path)
    destination = tmp_path / "reports"
    destination.mkdir()
    for filename in ("behavior.md", "behavior.csv"):
        (destination / filename).write_bytes(b"\xff unrelated binary")
    with pytest.raises(FileExistsError):
        write_behavior_report([record], destination, overwrite=True)
    assert (destination / "behavior.md").read_bytes() == b"\xff unrelated binary"
    assert (destination / "behavior.csv").read_bytes() == b"\xff unrelated binary"
