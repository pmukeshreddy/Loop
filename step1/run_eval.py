"""Small live Codex/RLM behavioral comparison; not a DeepSWE benchmark."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SOURCE = "def total(values):\n    return sum(values)\n"
INSTRUCTION = (
    "Fix total.py: total(values) must sum numbers while ignoring None entries. "
    "An empty iterable or only None entries returns 0. Support negative numbers, "
    "floats, zero, and generators. Change only total.py."
)
VERIFIER = """import runpy
total = runpy.run_path('total.py')['total']
assert total([1, None, 3]) == 4
assert total([]) == 0
assert total([None, None]) == 0
assert total([0, -5, None, 2.5]) == -2.5
assert total(x for x in [None, 2, 5]) == 7
print('PASS')
"""


def git(path: Path, *args: str, input: str | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        input=input,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout


def make_fixture(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "total.py").write_text(SOURCE)
    git(path, "init", "-q")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "Phase 1 fixture")
    git(path, "config", "core.hooksPath", "/dev/null")
    git(path, "add", "total.py")
    git(path, "commit", "-qm", "base")


def verify_patch(patch: str, path: Path) -> tuple[bool, str]:
    make_fixture(path)
    try:
        git(path, "apply", "--check", "-", input=patch)
        git(path, "apply", "-", input=patch)
    except subprocess.CalledProcessError as exc:
        return False, exc.stderr.strip()
    result = subprocess.run(
        [sys.executable, "-I", "-c", VERIFIER],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def submitted_patch(response: str, trajectory: dict) -> str:
    # The official loop can return fallback text at its iteration limit.
    for iteration in trajectory.get("iterations", []):
        if iteration.get("final_answer") == response and any(
            block.get("result", {}).get("final_answer") == response
            for block in iteration.get("code_blocks", [])
        ):
            return response
    raise ValueError("RLM ended without an executed answer submission")


def run_rlm(model: str, token: str, output: Path, timeout: float) -> tuple[str, dict]:
    from step1.codex import execute

    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="phase1-rlm-") as work:
        result = execute(
            [sys.executable, "-m", "step1.rlm_worker"],
            cwd=Path(work),
            prompt=json.dumps(
                {"model": model, "output": str(output.resolve()), "timeout": timeout}
            ),
            env={**os.environ, "PYTHONPATH": str(root), "DEEPSWE_OPENAI_TOKEN": token},
            timeout=timeout,
        )
    data = json.loads(result)
    return data["patch"], data["evidence"]


def complete_rlm(
    model: str, token: str, output: Path, timeout: float
) -> tuple[str, dict]:
    from rlm import RLM
    from rlm.logger import RLMLogger

    logger = RLMLogger(log_dir=str(output / "trajectory"))
    with RLM(
        backend="openai_responses",
        backend_kwargs={
            "model_name": model,
            "fixed_model": model,
            "api_key": token,
            "timeout": min(timeout, 60),
        },
        environment="local",
        max_depth=2,
        max_iterations=8,
        max_timeout=timeout,
        logger=logger,
    ) as rlm:
        result = rlm.completion(
            {"total.py": SOURCE},
            root_prompt=INSTRUCTION + "\nThe repository's original text is in context. "
            "Use the REPL to inspect it. Keep intermediate values across turns. "
            "Call llm_query on the relevant source, then rlm_query for an independent check. "
            "Submit a raw unified diff in answer['content'] and set answer['ready'] = True.",
        )
    trajectory = result.metadata or logger.get_trajectory()
    patch = submitted_patch(result.response, trajectory)
    calls = [
        call
        for iteration in trajectory["iterations"]
        for block in iteration.get("code_blocks", [])
        for call in block.get("result", {}).get("rlm_calls", [])
    ]
    evidence = {
        "repl_executed": any(i.get("code_blocks") for i in trajectory["iterations"]),
        "llm_query_called": any(
            not c.get("error") and not (c.get("metadata") or {}).get("iterations")
            for c in calls
        ),
        "rlm_query_called": any(
            not c.get("error") and bool((c.get("metadata") or {}).get("iterations"))
            for c in calls
        ),
        "submitted": True,
        "usage": result.usage_summary.to_dict(),
        "usage_scope": "root and plain subcalls; recursive child usage is recorded in the trajectory",
    }
    return patch, evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", required=True, help="Same explicit model ID for both arms"
    )
    parser.add_argument("--auth", choices=("chatgpt", "api-key"), default="chatgpt")
    parser.add_argument("--arm", choices=("codex", "rlm", "both"), default="both")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--output", type=Path, default=Path("step1/results/openai-behavior")
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    from step1.auth import credential
    from step1.codex import run

    token = credential(args.auth)
    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=args.output)).resolve()
    rows = []
    for arm in ("codex", "rlm") if args.arm == "both" else (args.arm,):
        started = time.monotonic()
        row = {"arm": arm, "model": args.model, "auth": args.auth, "passed": False}
        arm_output = output / arm
        arm_output.mkdir()
        try:
            with tempfile.TemporaryDirectory(prefix="phase1-") as work:
                work = Path(work)
                if arm == "codex":
                    repo = work / "repo"
                    make_fixture(repo)
                    row["usage"] = run(
                        repo, INSTRUCTION, args.model, token, args.timeout
                    )
                    git(repo, "add", "-A")
                    patch = git(repo, "diff", "--cached", "--binary", "HEAD")
                else:
                    patch, evidence = run_rlm(
                        args.model, token, arm_output, args.timeout
                    )
                    row.update(evidence)
                (arm_output / "model.patch").write_text(patch)
                row["verifier_passed"], row["verifier_output"] = verify_patch(
                    patch, work / "grade"
                )
                row["passed"] = row["verifier_passed"] and (
                    arm == "codex"
                    or all(
                        row[k]
                        for k in (
                            "repl_executed",
                            "llm_query_called",
                            "rlm_query_called",
                            "submitted",
                        )
                    )
                )
        except Exception as exc:  # noqa: BLE001 -- record failed arms without claiming success
            row["error"] = f"{type(exc).__name__}: {exc}".replace(token, "[REDACTED]")
        row["wall_time_sec"] = round(time.monotonic() - started, 3)
        rows.append(row)
        print(json.dumps(row), flush=True)
    (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Behavioral check only; no DeepSWE solve-rate claim. Results: {output}")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
