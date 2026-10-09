"""Offline, source-linked aggregation of supplied trajectory analyses.

This module performs no model inference, correctness scoring, or thresholding.
Unknown detector evidence stays out of known denominators. ``known`` and
``unknown`` count trajectories; ``denominator`` describes the metric's actual
units (trajectories, code blocks, or subcalls). CSV paths are absolute and the
Markdown report links the same files relative to its output directory.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import csv
import html
import io
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote


PHASES = ("before", "teacher", "after")
DIMENSIONS = ("family", "size_bucket", "domain")
DECOMPOSITIONS = ("direct_read", "regex_filter", "chunk_subcall", "whole_subcall", "other")
DETECTOR_NAMES = {
    "D1": "probe_first", "D2": "no_raw_dump", "D3": "code_search_before_read",
    "D4": "search_refinement", "D5": "windowed_reads", "D6": "chained_search",
    "D7": "verify_hit", "D8": "subcalls_on_chunks", "D9": "subcalls_in_loop",
    "D10": "batching_ok", "D11": "buffer_store", "D12": "vars_reused",
    "D13": "no_hand_copy", "D14": "aggregate_in_code", "D15": "clean_finish",
    "D16": "syntax_error_rate", "D17": "error_recovery", "D18": "coverage",
    "D19": "first_decomposition",
}
COUNT_FIELDS = ("subcall_count", "subcall_mean_prompt_chars", "subcall_max_prompt_chars",
                "truncation_events", "syntax_error_blocks", "code_blocks")
CSV_FIELDS = ("phase", "dimension", "group", "metric", "name", "category", "status",
              "value", "numerator", "denominator", "known", "unknown", "trajectories",
              "trajectory_paths")
REPORT_MARKER = "<!-- rlm-opsd:offline-behavior-report:v1 -->"


def _number(value: Any, field: str, *, integer: bool = False, fraction: bool = False) -> None:
    if value is None:
        return
    valid_type = type(value) is int if integer else type(value) in (int, float)
    try:
        finite = math.isfinite(value) if valid_type else False
    except OverflowError:
        finite = False
    if not valid_type or not finite or value < 0 or (fraction and value > 1):
        raise ValueError(f"{field} must be a finite nonnegative {'integer' if integer else 'number'}"
                         + (" in [0, 1]" if fraction else ""))


def _boolean(value: Any, field: str) -> None:
    if value is not None and type(value) is not bool:
        raise ValueError(f"{field} must be boolean or null")


def _validated_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result, seen = [], set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ValueError(f"record {index} must be a mapping")
        if record.get("phase") not in PHASES:
            raise ValueError(f"record {index}: phase must be before, teacher, or after")
        raw_path = record.get("trajectory_path")
        if not isinstance(raw_path, (str, os.PathLike)) or not str(raw_path):
            raise ValueError(f"record {index}: trajectory_path must identify an existing file")
        try:
            path = Path(raw_path).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"record {index}: trajectory_path does not resolve to a file") from exc
        if not path.is_file():
            raise ValueError(f"record {index}: trajectory_path must identify an existing file")
        if path in seen:
            raise ValueError(f"duplicate trajectory_path: {path}")
        seen.add(path)
        analysis = record.get("analysis")
        if not isinstance(analysis, Mapping):
            raise ValueError(f"record {index}: analysis must be a mapping")
        if not isinstance(analysis.get("task_id"), str) or not analysis["task_id"].strip():
            raise ValueError(f"record {index}: task_id must be a nonempty string")
        labels = {}
        for field in DIMENSIONS:
            label = analysis.get(field)
            if label is not None:
                valid = isinstance(label, str) and bool(label.strip())
                if field == "size_bucket":
                    valid = valid or (type(label) is int and label >= 0)
                if not valid:
                    raise ValueError(f"record {index}: {field} must be a label or null")
            labels[field] = "unknown" if label is None else str(label)
        detectors = analysis.get("detectors")
        if not isinstance(detectors, Mapping):
            raise ValueError(f"record {index}: detectors must be a mapping")
        for key in DETECTOR_NAMES:
            if key not in detectors:
                raise ValueError(f"record {index}: missing detector {key}; supply null for unknown")
            value = detectors[key]
            if key in ("D16", "D18"):
                _number(value, key, fraction=True)
            elif key == "D19":
                if value is not None and value not in DECOMPOSITIONS:
                    raise ValueError("D19 must be a supported decomposition category or null")
            else:
                _boolean(value, key)
        if "task_tag_match" not in analysis:
            raise ValueError("missing task_tag_match; supply null for unknown")
        _boolean(analysis["task_tag_match"], "task_tag_match")
        if "task_success" in record and type(record["task_success"]) is not bool:
            raise ValueError("task_success, when supplied, must be boolean")
        counts = analysis.get("counts")
        if not isinstance(counts, Mapping):
            raise ValueError("counts must be a mapping")
        for field in COUNT_FIELDS:
            if field not in counts:
                raise ValueError(f"missing counts.{field}; supply null for unknown")
            _number(counts[field], field, integer=field != "subcall_mean_prompt_chars")
        blocks, errors = counts["code_blocks"], counts["syntax_error_blocks"]
        if blocks is not None and errors is not None:
            if errors > blocks:
                raise ValueError("syntax_error_blocks cannot exceed code_blocks")
            if detectors["D16"] is not None:
                expected = errors / blocks if blocks else 0.0
                if not math.isclose(detectors["D16"], expected, rel_tol=1e-9, abs_tol=1e-12):
                    raise ValueError("D16 disagrees with syntax_error_blocks / code_blocks")
        calls, mean, maximum = (counts[key] for key in
                                ("subcall_count", "subcall_mean_prompt_chars", "subcall_max_prompt_chars"))
        if mean is not None and maximum is not None and mean > maximum:
            raise ValueError("subcall_mean_prompt_chars cannot exceed subcall_max_prompt_chars")
        if calls is not None and mean is not None and maximum is not None:
            total_chars = calls * mean
            if maximum > total_chars and not math.isclose(maximum, total_chars):
                raise ValueError("subcall_max_prompt_chars cannot exceed total prompt chars")
        if calls == 0 and (mean not in (None, 0) or maximum not in (None, 0)):
            raise ValueError("zero subcall_count requires zero or null prompt statistics")
        lower_bound = analysis.get("coverage_lower_bound")
        _number(lower_bound, "coverage_lower_bound", fraction=True)
        if lower_bound is not None and detectors["D18"] is not None and lower_bound > detectors["D18"]:
            raise ValueError("coverage_lower_bound cannot exceed exact D18 coverage")
        result.append({"phase": record["phase"], "trajectory_path": str(path),
                       "labels": labels, "analysis": analysis,
                       "task_success": record.get("task_success")})
    return result


def _group_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []

    def add(metric: str, values: list[Any], *, mode: str = "mean", category: str = "",
            numerators: list[float | int] | None = None,
            denominators: list[float | int] | None = None) -> None:
        known = len(values)
        if mode == "pooled":
            numerator, denominator = math.fsum(numerators or []), sum(denominators or [])
            value = numerator / denominator if denominator else None
        elif mode == "max":
            numerator, denominator = None, sum(denominators or [])
            samples = [value for value in values if value is not None]
            value = max(samples) if samples else None
        elif mode == "sum":
            numerator, denominator = None, None
            value = sum(values) if known else None
        else:
            numerator, denominator = sum(values), known
            value = numerator / denominator if denominator else None
        if value is not None and not math.isfinite(value):
            raise ValueError(f"aggregate {metric} is not finite")
        if not records:
            numerator, denominator = None, None
        unknown = len(records) - known
        status = ("not run" if not records else "unknown" if not known
                  else "no observations" if value is None else "partial" if unknown else "measured")
        rows.append({"metric": metric, "name": DETECTOR_NAMES.get(metric, metric),
                     "category": category, "status": status, "value": value,
                     "numerator": numerator, "denominator": denominator,
                     "known": known, "unknown": unknown})

    for detector in DETECTOR_NAMES:
        values = [record["analysis"]["detectors"][detector] for record in records
                  if record["analysis"]["detectors"][detector] is not None]
        if detector == "D16":
            analyses = [record["analysis"] for record in records
                        if record["analysis"]["detectors"]["D16"] is not None
                        and record["analysis"]["counts"]["syntax_error_blocks"] is not None
                        and record["analysis"]["counts"]["code_blocks"] is not None]
            add(detector, analyses, mode="pooled",
                numerators=[item["counts"]["syntax_error_blocks"] for item in analyses],
                denominators=[item["counts"]["code_blocks"] for item in analyses])
        elif detector == "D19":
            for category in DECOMPOSITIONS:
                add(detector, [value == category for value in values], category=category)
        else:
            add(detector, values)
    for field in ("task_tag_match", "task_success", "coverage_lower_bound"):
        values = [record.get(field) if field == "task_success" else record["analysis"].get(field)
                  for record in records]
        add(field, [value for value in values if value is not None])
    counts = [record["analysis"]["counts"] for record in records]
    call_counts = [item["subcall_count"] for item in counts if item["subcall_count"] is not None]
    add("subcall_count", call_counts, mode="sum")
    add("subcall_mean_count", call_counts)
    for key, mode in (("subcall_mean_prompt_chars", "pooled"), ("subcall_max_prompt_chars", "max")):
        known = [item for item in counts if item["subcall_count"] is not None
                 and (item["subcall_count"] == 0 or item[key] is not None)]
        values = [item[key] if item["subcall_count"] else None for item in known]
        add(key, values, mode=mode,
            numerators=[item[key] * item["subcall_count"] if item["subcall_count"] else 0
                        for item in known],
            denominators=[item["subcall_count"] for item in known])
    add("truncation_events", [item["truncation_events"] for item in counts
                              if item["truncation_events"] is not None], mode="sum")
    return rows


def aggregate_behavior(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return long-form rows for every phase and observed breakdown label.

    A source path may occur only once, including across phases: duplicating one
    trajectory would double-count evidence. Distinct rollouts of the same task
    are allowed. Missing labels are grouped as ``unknown``. Empty phase/group
    combinations carry ``not run`` with null values, never measured zeros.
    """
    records = _validated_records(records)
    groups = [("overall", "all")]
    for dimension in DIMENSIONS:
        groups.extend((dimension, label) for label in sorted({record["labels"][dimension]
                                                              for record in records}))
    rows = []
    for phase in PHASES:
        for dimension, label in groups:
            members = [record for record in records if record["phase"] == phase
                       and (dimension == "overall" or record["labels"][dimension] == label)]
            paths = [record["trajectory_path"] for record in members]
            for row in _group_metrics(members):
                rows.append({"phase": phase, "dimension": dimension, "group": label,
                             **row, "trajectories": len(members), "trajectory_paths": paths})
    return rows


def _escape(text: Any) -> str:
    return (html.escape(str(text), quote=False).replace("\\", "\\\\")
            .replace("|", "\\|").replace("\n", " ").replace("\r", " ")
            .replace("[", "\\[").replace("]", "\\]").replace("`", "\\`"))


def _format(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def _markdown(rows: list[dict[str, Any]], output_dir: Path, source_label: str) -> str:
    lines = [REPORT_MARKER, "# Offline behavior report", "", _escape(source_label), "",
             "Aggregated from supplied analyses; this writer performs no model runs. "
             "Rates describe supplied detector evidence, including its unknowns. "
             "Task success is tracked only when explicitly supplied.", "",
             "Known/unknown count trajectories. Boolean rates and coverage means use known "
             "trajectories; syntax-error rates pool erroneous blocks over code blocks. "
             "Prompt means weight by actual subcall counts; prompt maxima use observed calls. "
             "Coverage lower bounds remain separate from exact coverage. Missing runs are "
             "marked `not run`; zero code blocks or subcalls give no rate or prompt statistic. "
             "D19 category proportions use known categories.", ""]
    current_group = None
    anchor = 0
    for row in rows:
        group = (row["phase"], row["dimension"], row["group"])
        if group != current_group:
            current_group = group
            anchor += 1
            lines.extend(["", f"## {_escape(group[0])} / {_escape(group[1])}: {_escape(group[2])}", "",
                          f'<a id="sources-{anchor}"></a>', "", "Source trajectories:", ""])
            if row["trajectory_paths"]:
                for source in row["trajectory_paths"]:
                    relative = os.path.relpath(source, output_dir.resolve())
                    lines.append(f"- [{_escape(Path(source).name)}]({quote(relative, safe='/')})")
            else:
                lines.append("not run")
            lines.extend(["", "| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |",
                          "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |"])
        name = row["metric"] + (" — " + row["name"] if row["name"] != row["metric"] else "")
        if row["category"]:
            name += ": " + row["category"]
        sources = f"[logs](#sources-{anchor})" if row["trajectory_paths"] else "not run"
        lines.append("| " + " | ".join([_escape(name), *[_format(row[key]) for key in
                     ("value", "numerator", "denominator", "known", "unknown")], row["status"], sources]) + " |")
    return "\n".join(lines) + "\n"


def _check_outputs(paths: dict[str, Path], overwrite: bool, source_paths: set[str]) -> None:
    for path in paths.values():
        if path.is_symlink() or str(path.resolve()) in source_paths:
            raise FileExistsError(f"Refusing to replace source file or symlink: {path}")
        if path.exists() and (not overwrite or not path.is_file()):
            raise FileExistsError(f"Report output already exists: {path}")
    if any(path.exists() for path in paths.values()):
        owned = all(path.is_file() for path in paths.values())
        if owned:
            try:
                owned = paths["markdown"].read_text(encoding="utf-8").startswith(REPORT_MARKER + "\n")
                with paths["csv"].open(newline="", encoding="utf-8") as handle:
                    owned = owned and next(csv.reader(handle), []) == list(CSV_FIELDS)
            except (UnicodeError, csv.Error):
                owned = False
        if not owned:
            raise FileExistsError("Refusing to overwrite files that are not this writer's complete report")


def write_behavior_report(records: Iterable[Mapping[str, Any]], output_dir: str | os.PathLike[str], *,
                          source_label: str = "Supplied trajectory analyses (offline; no model runs performed)",
                          overwrite: bool = False) -> dict[str, Path]:
    """Write ``behavior.md`` and ``behavior.csv`` and return their paths.

    All records are validated and rendered before creating outputs. Existing
    files are refused by default. ``overwrite=True`` accepts only a complete
    prior report bearing this writer's marker/header, never source trajectories
    or symlinks. Other files in the output directory are untouched. Use an
    explicit source label for hand-labelled fixtures, not a model-result label.
    """
    if not isinstance(source_label, str) or not source_label.strip():
        raise ValueError("source_label must be a nonempty string")
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be boolean")
    rows = aggregate_behavior(records)
    output_dir = Path(output_dir)
    paths = {"markdown": output_dir / "behavior.md", "csv": output_dir / "behavior.csv"}
    source_paths = {source for row in rows for source in row["trajectory_paths"]}
    _check_outputs(paths, overwrite, source_paths)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "trajectory_paths": json.dumps(row["trajectory_paths"], ensure_ascii=False)})
    contents = {"markdown": _markdown(rows, output_dir, source_label), "csv": buffer.getvalue()}
    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite and any(path.exists() for path in paths.values()):
        temporary = []
        try:
            for key, path in paths.items():
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                                 dir=output_dir, delete=False) as handle:
                    temporary.append((Path(handle.name), path))
                    handle.write(contents[key])
            _check_outputs(paths, overwrite, source_paths)
            for temporary_path, path in temporary:
                os.replace(temporary_path, path)
        finally:
            for temporary_path, _ in temporary:
                temporary_path.unlink(missing_ok=True)
    else:
        created = []
        try:
            for key, path in paths.items():
                with path.open("x", encoding="utf-8", newline="") as handle:
                    created.append(path)
                    handle.write(contents[key])
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise
    return paths
