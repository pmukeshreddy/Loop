"""Run the native Codex harness using the same OpenAI model and credential."""

import json
import os
import signal
import subprocess
from pathlib import Path


def execute(
    command: list[str], *, cwd: Path, prompt: str, env: dict, timeout: float
) -> str:
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        if process.returncode:
            raise RuntimeError(
                f"Harness process exited {process.returncode}: {stderr[-1500:]}"
            )
    return stdout


def command(model: str, sandbox: str = "workspace-write") -> list[str]:
    return [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--skip-git-repo-check",
        "--json",
        "--sandbox",
        sandbox,
        "--model",
        model,
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="medium"',
        "-c",
        'model_provider="phase1"',
        "-c",
        'model_providers.phase1.name="Refine DeepSWE"',
        "-c",
        'model_providers.phase1.base_url="https://api.openai.com/v1"',
        "-c",
        'model_providers.phase1.env_key="DEEPSWE_OPENAI_TOKEN"',
        "-c",
        'model_providers.phase1.wire_api="responses"',
        "-c",
        "model_providers.phase1.requires_openai_auth=false",
        "-c",
        "model_providers.phase1.supports_websockets=false",
        "-c",
        "features.apps=false",
        "-c",
        "features.multi_agent=false",
        "-c",
        "features.hooks=false",
        "-c",
        'web_search="disabled"',
        "-",
    ]


def completed_usage(events: str) -> dict:
    usage = None
    for line in events.splitlines():
        event = json.loads(line)
        if event["type"] in {"turn.failed", "error"}:
            raise RuntimeError(f"Codex turn failed: {event}")
        if event["type"] == "turn.completed":
            usage = event["usage"]
    if usage is None:
        raise RuntimeError("Codex ended without a completed turn")
    return usage


def run(
    checkout: Path, instruction: str, model: str, token: str, timeout: float
) -> dict:
    events = execute(
        command(model),
        cwd=checkout,
        prompt=instruction,
        env={**os.environ, "DEEPSWE_OPENAI_TOKEN": token},
        timeout=timeout,
    )
    return completed_usage(events)
