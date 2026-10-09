"""Run one native harness inside its clean task container."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from step1.run_eval import git, submitted_patch


def repository_context(repo: Path) -> dict[str, str]:
    context = {}
    for name in git(repo, "ls-files", "-z").split("\0"):
        path = repo / name
        if not name or path.is_symlink() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        if "\0" not in content:
            context[name] = content
    return context


def capture_patch(repo: Path, base: str) -> str:
    with tempfile.TemporaryDirectory(prefix="phase1-index-") as work:
        index = Path(work) / "index"
        source = repo / git(repo, "rev-parse", "--git-path", "index").strip()
        shutil.copyfile(source, index)
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo,
            env=env,
            capture_output=True,
            check=True,
            timeout=60,
        )
        return subprocess.run(
            ["git", "diff", "--cached", "--binary", base],
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout


def read_usage(path: Path) -> dict:
    records = [json.loads(line) for line in path.read_text().splitlines()]
    return {
        "calls": len(records),
        "input_tokens": sum(r["input_tokens"] for r in records),
        "output_tokens": sum(r["output_tokens"] for r in records),
    }


def solve_rlm(model: str, instruction: str, timeout: float, output: Path) -> dict:
    from rlm import RLM
    from rlm.logger import RLMLogger

    context = repository_context(Path("/app"))
    logger = RLMLogger(log_dir=str(output / "trajectory"))
    with RLM(
        backend="openai_responses",
        backend_kwargs={
            "model_name": model,
            "fixed_model": model,
            "api_key": os.environ["DEEPSWE_OPENAI_TOKEN"],
            "timeout": 120,
            "reasoning_effort": "medium",
            "usage_log_path": str(output / "usage.jsonl"),
        },
        environment="local",
        max_depth=2,
        max_iterations=30,
        max_timeout=timeout,
        max_concurrent_subcalls=1,
        logger=logger,
    ) as rlm:
        result = rlm.completion(
            context,
            root_prompt=instruction
            + "\n\nThe repository is /app. context maps its original tracked text files to their contents. "
            "Use the REPL and your built-in model calls to inspect and solve the task. "
            "Make actual file edits in /app; use absolute paths or subprocess.run(..., cwd='/app'). "
            "You may run the repository's available tests using subprocess. "
            "Your changes on disk are the submission. Finish by setting answer['content'] to a short summary "
            "and answer['ready'] = True in a repl block. "
            f"You have {int(timeout)} seconds total, including all subcalls.",
        )
    trajectory = result.metadata or logger.get_trajectory()
    (output / "answer.txt").write_text(result.response)
    submitted_patch(result.response, trajectory)
    return {
        "status": "completed",
        "usage": read_usage(output / "usage.jsonl"),
        "usage_complete": True,
    }


def solve_codex(model: str, instruction: str, output: Path) -> dict:
    from step1.codex import command, completed_usage

    # Docker is the external sandbox; the CLI needs ordinary access inside it.
    with (
        (output / "events.jsonl").open("w") as events,
        (output / "codex-stderr.txt").open("w") as errors,
    ):
        process = subprocess.run(
            command(model, "danger-full-access"),
            cwd="/app",
            input=instruction,
            text=True,
            stdout=events,
            stderr=errors,
            check=False,
        )
    if process.returncode:
        raise RuntimeError(f"Codex exited {process.returncode}; see codex-stderr.txt")
    return {
        "status": "completed",
        "usage": completed_usage((output / "events.jsonl").read_text()),
        "usage_complete": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("solve", "capture"))
    parser.add_argument("--arm", choices=("codex", "rlm"))
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--base")
    args = parser.parse_args()
    if args.operation == "capture":
        print(capture_patch(Path("/app"), args.base), end="")
        return
    output = Path("/logs/agent")
    instruction = Path("/instruction.md").read_text()
    instruction += f"\n\nWork in /app. You have {int(args.timeout)} seconds. Your on-disk changes will be collected when you finish or reach the deadline."
    try:
        result = (
            solve_codex(args.model, instruction, output)
            if args.arm == "codex"
            else solve_rlm(args.model, instruction, args.timeout, output)
        )
    except Exception as exc:  # noqa: BLE001 -- save model failures before collection
        token = os.environ.get("DEEPSWE_OPENAI_TOKEN", "")
        error = f"{type(exc).__name__}: {exc}"
        result = {
            "status": "error",
            "error": error.replace(token, "[REDACTED]") if token else error,
            "usage_complete": False,
        }
    temporary = output / "worker.json.tmp"
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(output / "worker.json")


if __name__ == "__main__":
    main()
