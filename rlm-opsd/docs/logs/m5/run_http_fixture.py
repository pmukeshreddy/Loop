"""Reproduce the M5 CLI demonstration. Synthetic HTTP replies, not model results.

Run once from the repository: .venv/bin/python docs/logs/m5/run_http_fixture.py
Requires a new docs/logs/m5/http-fixture directory; never overwrites evidence.
"""
import asyncio
import json
from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HELPERS = runpy.run_path(str(ROOT / "tests/test_teacher_gate.py"))


async def main():
    directory = ROOT / "docs/logs/m5/http-fixture"
    directory.mkdir(exist_ok=False)
    server, config, requests = await HELPERS["serve_fixture"](directory / "inputs")
    output = directory / "report"
    command = ["make", "teacher-gate", f"GATE_CONFIG={config}", f"GATE_OUTPUT={output}"]
    print("Source: TEST HTTP FIXTURE; NOT MODEL RESULTS", flush=True)
    print("Command argv: " + json.dumps(command), flush=True)
    try:
        process = await asyncio.create_subprocess_exec(
            *command, cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        stdout, _ = await process.communicate()
        print(stdout.decode(), end="", flush=True)
    finally:
        await server.cleanup()
    assert process.returncode == 0, process.returncode
    result = json.loads((output / "gate.json").read_text())
    assert result["status"] == "passed" and result["completed_episodes"] == 12
    root_calls = sum(path.startswith("/root") for path, _ in requests)
    leaf_calls = sum(path.startswith("/leaf") for path, _ in requests)
    assert (root_calls, leaf_calls) == (24, 12)
    evidence = dict(source="TEST HTTP FIXTURE; NOT MODEL RESULTS", completed_episodes=12,
                    root_generation_requests=root_calls, leaf_generation_requests=leaf_calls)
    (directory / "fixture-summary.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
