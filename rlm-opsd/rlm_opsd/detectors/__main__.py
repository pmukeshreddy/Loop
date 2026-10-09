"""Offline detector CLI: analyze supplied logs and write source-linked reports."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

import yaml

from .config import DetectorConfig
from .reports import PHASES, write_behavior_report


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON error in {path}: {exc}") from exc


def _load_manifest(path: Path) -> list[dict]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError("manifest must be a JSON list of records")
    records, seen = [], set()
    allowed = {"phase", "trajectory_path", "task_success", "task_metadata"}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"manifest record {index} must be an object")
        extra = item.keys() - allowed
        if extra:
            raise ValueError(f"manifest record {index} contains unknown fields: {', '.join(sorted(extra))}")
        if item.get("phase") not in PHASES:
            raise ValueError(f"manifest record {index}: phase must be before, teacher, or after")
        source = item.get("trajectory_path")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"manifest record {index}: trajectory_path must be a nonempty string")
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = path.parent / source_path
        source_path = source_path.resolve(strict=True)
        if not source_path.is_file():
            raise ValueError(f"manifest record {index}: trajectory_path must identify a file: {source_path}")
        if source_path in seen:
            raise ValueError(f"manifest record {index}: duplicate trajectory_path: {source_path}")
        seen.add(source_path)
        if "task_success" in item and type(item["task_success"]) is not bool:
            raise ValueError(f"manifest record {index}: task_success must be boolean when supplied")
        if "task_metadata" in item and not isinstance(item["task_metadata"], dict):
            raise ValueError(f"manifest record {index}: task_metadata must be an object when supplied")
        records.append({**item, "trajectory_path": source_path})
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze supplied trajectory logs offline and write behavior reports; no model calls.")
    parser.add_argument("--config", required=True, help="Explicit detector threshold YAML; no defaults are filled")
    parser.add_argument("--manifest", required=True,
                        help="JSON list of phase/trajectory_path records; paths are relative to this manifest")
    parser.add_argument("--output", required=True, help="Directory for behavior.md and behavior.csv")
    parser.add_argument("--source-label", required=True,
                        help="Description of the supplied evidence; explicitly label hand-authored fixtures")
    parser.add_argument("--overwrite", action="store_true", help="Replace only this writer's existing report")
    args = parser.parse_args(argv)
    try:
        config = DetectorConfig.from_yaml(args.config)
        manifest = _load_manifest(Path(args.manifest))
        from . import analyze_trajectory

        records = []
        for item in manifest:
            trace = _read_json(item["trajectory_path"])
            if not isinstance(trace, dict):
                raise ValueError(f"trajectory {item['trajectory_path']} must be a JSON object")
            record = {"phase": item["phase"], "trajectory_path": item["trajectory_path"],
                      "analysis": analyze_trajectory(trace, config, task_metadata=item.get("task_metadata"))}
            if "task_success" in item:
                record["task_success"] = item["task_success"]
            records.append(record)
        paths = write_behavior_report(records, args.output, source_label=args.source_label,
                                      overwrite=args.overwrite)
    except yaml.YAMLError as exc:
        print(f"YAML error in {args.config}: {exc}", file=sys.stderr)
        return 1
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: str(path) for key, path in paths.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
