"""Run the fixed eight-task DeepSWE pilot with native Codex and official RLM."""

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "data/deep-swe/tasks"
RUNTIME = ROOT / "step1/work/openai-runtime"
PYTHON = "/opt/phase1-venv/bin/python"


def docker(*args: str, timeout: float = 120, check: bool = True, **kwargs):
    return subprocess.run(
        ["docker", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
        **kwargs,
    )


def read_grade(verifier: Path) -> dict:
    path = verifier / "reward.json"
    if not path.exists():
        raise RuntimeError(
            "Verifier produced no reward.json; inspect verifier/test-stdout.txt"
        )
    reward = json.loads(path.read_text())
    if reward.get("reward") not in (0, 1):
        raise RuntimeError(f"Invalid verifier reward: {reward.get('reward')}")
    return reward


def worker_result(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return {
            "status": "error",
            "usage_complete": False,
            "error": f"Worker telemetry unavailable: {type(exc).__name__}",
        }


def tasks() -> list[dict]:
    selected = json.loads((ROOT / "step1/results/slice.json").read_text())["tasks"]
    if len(selected) != 8 or len({task["task_id"] for task in selected}) != 8:
        raise ValueError("Expected the fixed eight distinct tasks")
    for task in selected:
        config = tomllib.loads((TASKS / task["task_id"] / "task.toml").read_text())
        if (
            config["metadata"]["base_commit_hash"] != task["base_commit_hash"]
            or config["environment"]["docker_image"] != task["docker_image"]
        ):
            raise ValueError(f"Task metadata changed: {task['task_id']}")
    return selected


def prepare(selected: list[dict]) -> dict[str, str]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    metadata = json.load(
        urllib.request.urlopen(
            "https://registry.npmjs.org/@openai/codex/0.162.0-linux-x64", timeout=30
        )
    )
    archive = RUNTIME / "codex.tgz"
    if not archive.exists():
        urllib.request.urlretrieve(metadata["dist"]["tarball"], archive)
    expected = metadata["dist"]["integrity"].removeprefix("sha512-")
    if (
        base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()
        != expected
    ):
        raise ValueError("Codex archive integrity mismatch")
    if not (RUNTIME / "package/vendor/x86_64-unknown-linux-musl/bin/codex").exists():
        with tarfile.open(archive) as tar:
            tar.extractall(RUNTIME, filter="data")
    source = RUNTIME / "harness"
    (source / "step1").mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "step1").glob("*.py"):
        shutil.copy2(path, source / "step1" / path.name)
    shutil.copytree(
        ROOT / "third_party/rlm/rlm",
        source / "rlm",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (RUNTIME / ".dockerignore").write_text("codex.tgz\n")
    common = RUNTIME / "Dockerfile.tools"
    common.write_text(
        f"FROM {selected[0]['docker_image']}\n"
        "RUN python3 -m venv /opt/phase1-venv && /opt/phase1-venv/bin/pip install --no-cache-dir openai==3.26.0 python-dotenv==1.2.1 rich==14.3.3 requests==2.32.5\n"
        "COPY package/vendor/x86_64-unknown-linux-musl /opt/codex\n"
        "COPY harness /opt/harness\n"
    )
    print("Preparing shared Codex/RLM runtime", flush=True)
    with (RUNTIME / "build.log").open("w") as log:
        subprocess.run(
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                "deepswe-openai-tools:phase1",
                "-f",
                str(common),
                str(RUNTIME),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=900,
        )
        images = {}
        for task in selected:
            tag = "deepswe-openai:" + task["task_id"]
            recipe = RUNTIME / "Dockerfile.task"
            recipe.write_text(
                f"FROM {task['docker_image']}\n"
                "COPY --from=deepswe-openai-tools:phase1 /opt/phase1-venv /opt/phase1-venv\n"
                "COPY --from=deepswe-openai-tools:phase1 /opt/codex /opt/codex\n"
                "COPY --from=deepswe-openai-tools:phase1 /opt/harness /opt/harness\n"
                'ENV PATH="/opt/codex/bin:/opt/codex/codex-path:${PATH}"\n'
                "ENV PYTHONPATH=/opt/harness\n"
            )
            subprocess.run(
                [
                    "docker",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "-t",
                    tag,
                    "-f",
                    str(recipe),
                    str(RUNTIME),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=600,
            )
            images[task["task_id"]] = docker(
                "image", "inspect", tag, "--format", "{{.Id}}"
            ).stdout.strip()
            print("Prepared " + task["task_id"], flush=True)
    (RUNTIME / "images.json").write_text(json.dumps(images, indent=2))
    return images


@contextmanager
def api_network():
    suffix = uuid.uuid4().hex[:10]
    network, proxy = "phase1-net-" + suffix, "phase1-api-" + suffix
    docker("network", "create", "--internal", network)
    try:
        docker(
            "run",
            "-d",
            "--name",
            proxy,
            "--platform",
            "linux/amd64",
            "--network",
            "bridge",
            "--entrypoint",
            "python3",
            "deepswe-openai-tools:phase1",
            "/opt/harness/step1/api_proxy.py",
        )
        docker("network", "connect", "--alias", "api-gateway", network, proxy)
        yield network
    finally:
        docker("rm", "-f", proxy, check=False)
        docker("network", "rm", network, check=False)


def run_process(
    command: list[str], log: Path, timeout: float, env=None
) -> tuple[int | None, bool]:
    with log.open("w") as stream:
        try:
            result = subprocess.run(
                command,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env=env,
                check=False,
            )
            return result.returncode, False
        except subprocess.TimeoutExpired:
            return None, True


def grade(task: dict, output: Path) -> dict:
    verifier = output / "verifier"
    verifier.mkdir(exist_ok=True)
    name = "phase1-grade-" + uuid.uuid4().hex[:10]
    command = [
        "docker",
        "run",
        "--name",
        name,
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--cpus",
        "2",
        "--memory",
        "3g",
        "-v",
        f"{TASKS / task['task_id'] / 'tests'}:/tests:ro",
        "-v",
        f"{output / 'artifacts'}:/logs/artifacts:ro",
        "-v",
        f"{verifier}:/logs/verifier",
        task["docker_image"],
        "bash",
        "/tests/test.sh",
    ]
    try:
        code, timed_out = run_process(
            command, verifier / "test-stdout.txt", task["verifier_timeout_sec"]
        )
        state = json.loads(
            docker("inspect", name, "--format", "{{json .State}}").stdout
        )
        if timed_out or state["OOMKilled"] or code != 0:
            raise RuntimeError(
                f"Verifier infrastructure failure: exit={code}, timeout={timed_out}, oom={state['OOMKilled']}"
            )
        return read_grade(verifier)
    finally:
        docker("rm", "-f", name, check=False)


def attempt(
    task: dict,
    arm: str,
    image: str,
    network: str,
    output: Path,
    model: str,
    timeout: float,
) -> dict:
    from step1.auth import credential

    agent = output / "agent"
    agent.mkdir(parents=True)
    artifacts = output / "artifacts"
    artifacts.mkdir()
    name = "phase1-agent-" + uuid.uuid4().hex[:10]
    row = {
        "task": task["task_id"],
        "arm": arm,
        "model": model,
        "timeout_sec": timeout,
        "status": "setup_error",
        "solved": False,
    }
    token = credential("chatgpt", min_validity=timeout + 60)
    try:
        docker(
            "run",
            "-d",
            "--init",
            "--name",
            name,
            "--platform",
            "linux/amd64",
            "--network",
            network,
            "--cpus",
            "2",
            "--memory",
            "3g",
            "-e",
            "HTTPS_PROXY=http://api-gateway:8080",
            "-e",
            "HTTP_PROXY=http://api-gateway:8080",
            "-e",
            "NO_PROXY=localhost,127.0.0.1",
            "-v",
            f"{agent}:/logs/agent",
            "-v",
            f"{TASKS / task['task_id'] / 'instruction.md'}:/instruction.md:ro",
            image,
            "sleep",
            "infinity",
        )
        actual = docker(
            "exec", name, "git", "-C", "/app", "rev-parse", "HEAD"
        ).stdout.strip()
        dirty = docker(
            "exec", name, "git", "-C", "/app", "status", "--porcelain"
        ).stdout
        if actual != task["base_commit_hash"] or dirty:
            raise RuntimeError("Agent image is not clean at the specified base commit")
        docker(
            "exec",
            name,
            "bash",
            "-lc",
            "cd /app && git config user.email phase1@example.invalid && git config user.name 'Phase 1' && git config core.hooksPath /dev/null && git checkout -b phase1",
        )
        command = [
            "docker",
            "exec",
            "-e",
            "DEEPSWE_OPENAI_TOKEN",
            name,
            PYTHON,
            "-m",
            "step1.benchmark_worker",
            "solve",
            "--arm",
            arm,
            "--model",
            model,
            "--timeout",
            str(timeout),
        ]
        started = time.monotonic()
        code, timed_out = run_process(
            command,
            agent / "process.log",
            timeout,
            env={**os.environ, "DEEPSWE_OPENAI_TOKEN": token},
        )
        row["wall_time_sec"] = round(time.monotonic() - started, 3)
        row["process_exit_code"] = code
        state = json.loads(
            docker("inspect", name, "--format", "{{json .State}}").stdout
        )
        # Stop every model-spawned process before collecting the deadline snapshot.
        docker("kill", name, check=False)
        docker("start", name)
        patch = docker(
            "exec",
            name,
            PYTHON,
            "-m",
            "step1.benchmark_worker",
            "capture",
            "--base",
            task["base_commit_hash"],
            timeout=120,
        ).stdout
        (artifacts / "model.patch").write_text(patch)
        row.update(worker_result(agent / "worker.json"))
        if timed_out:
            row["status"] = "timeout"
            row["usage_complete"] = False
        if state["OOMKilled"]:
            row["status"] = "memory_limit"
            row["usage_complete"] = False
        if arm == "rlm" and (agent / "usage.jsonl").exists():
            from step1.benchmark_worker import read_usage

            row["usage"] = read_usage(agent / "usage.jsonl")
    except Exception as exc:  # noqa: BLE001 -- preserve each failed attempt
        row["error"] = f"{type(exc).__name__}: {exc}".replace(token, "[REDACTED]")
    finally:
        docker("rm", "-f", name, check=False)
    if (artifacts / "model.patch").exists():
        try:
            row["grade"] = grade(task, output)
            row["solved"] = row["grade"]["reward"] == 1
        except Exception as exc:  # noqa: BLE001 -- distinguish verifier failures
            row["grading_error"] = f"{type(exc).__name__}: {exc}"
    (output / "result.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    selected = tasks()
    if args.prepare:
        prepare(selected)
        return
    images = json.loads((RUNTIME / "images.json").read_text())
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    base = ROOT / "step1/results/openai-eight"
    base.mkdir(parents=True, exist_ok=True)
    output = (
        args.output.resolve()
        if args.output
        else Path(tempfile.mkdtemp(prefix="run-", dir=base))
    )
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise ValueError("Refusing to overwrite an existing run")
    manifest = {
        "tasks": selected,
        "images": images,
        "model": args.model,
        "reasoning_effort": "medium",
        "auth": "chatgpt",
        "timeout_sec": args.timeout,
        "cpus": 2,
        "memory": "3g",
        "codex_version": "0.162.0",
        "rlm_max_depth": 2,
        "rlm_max_iterations": 30,
        "rlm_max_concurrent_subcalls": 1,
        "network": "OpenAI API only; verifier offline",
        "submission": "working tree at completion/deadline",
        "attempts_per_arm_per_task": 1,
        "rlm_commit": subprocess.check_output(
            ["git", "-C", str(ROOT / "third_party/rlm"), "rev-parse", "HEAD"], text=True
        ).strip(),
        "responses_client_sha256": hashlib.sha256(
            (ROOT / "third_party/rlm/rlm/clients/openai_responses.py").read_bytes()
        ).hexdigest(),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "step1").glob("*.py"))
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Results: {output}", flush=True)
    rows = []
    with api_network() as network:
        for index, task in enumerate(selected):
            for arm in ("codex", "rlm") if index % 2 == 0 else ("rlm", "codex"):
                print(f"START {task['task_id']} {arm}", flush=True)
                row = attempt(
                    task,
                    arm,
                    images[task["task_id"]],
                    network,
                    output / task["task_id"] / arm,
                    args.model,
                    args.timeout,
                )
                rows.append(row)
                (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(json.dumps(row), flush=True)
    print("All sixteen attempts recorded.", flush=True)


if __name__ == "__main__":
    main()
