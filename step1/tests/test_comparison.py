"""Small end-to-end behavior checks for the phase-one entry point."""

import json
import subprocess

import pytest

from step1 import run_eval

PATCH = "--- a/total.py\n+++ b/total.py\n@@ -1,2 +1,2 @@\n def total(values):\n-    return sum(values)\n+    return sum(value for value in values if value is not None)\n"


def test_verifier_accepts_correct_patch_and_rejects_empty_or_wrong_patch(tmp_path):
    assert run_eval.verify_patch(PATCH, tmp_path / "correct")[0]
    assert not run_eval.verify_patch("", tmp_path / "empty")[0]
    assert not run_eval.verify_patch(
        PATCH.replace(
            "return sum(value for value in values if value is not None)", "return 4"
        ),
        tmp_path / "constant",
    )[0]


def test_rlm_fallback_text_does_not_count_as_an_executed_submission():
    with pytest.raises(ValueError, match="submission"):
        run_eval.submitted_patch(
            PATCH, {"iterations": [{"final_answer": None, "code_blocks": []}]}
        )


def test_codex_requires_completed_turn_and_keeps_credential_out_of_arguments(
    monkeypatch, tmp_path
):
    from step1 import codex

    calls = []

    def execute(command, **kwargs):
        calls.append((command, kwargs))
        return json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 3},
            }
        )

    monkeypatch.setattr(codex, "execute", execute)
    assert (
        codex.run(tmp_path, "Fix total", "same-model", "secret", 30)["output_tokens"]
        == 3
    )
    command, options = calls[0]
    assert "secret" not in " ".join(command)
    assert options["env"]["DEEPSWE_OPENAI_TOKEN"] == "secret"
    assert command[command.index("--model") + 1] == "same-model"
    assert command[command.index("--sandbox") + 1] == "workspace-write"

    monkeypatch.setattr(
        codex, "execute", lambda *a, **kw: json.dumps({"type": "turn.failed"})
    )
    with pytest.raises(RuntimeError, match="failed|complete"):
        codex.run(tmp_path, "Fix total", "same-model", "secret", 30)


def test_codex_process_timeout_is_a_failure(tmp_path):
    import os
    import sys

    from step1 import codex

    with pytest.raises(subprocess.TimeoutExpired):
        codex.execute(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            cwd=tmp_path,
            prompt="",
            env=os.environ.copy(),
            timeout=0.1,
        )


def test_rlm_process_deadline_stops_hanging_execution(monkeypatch, tmp_path):
    import sys

    from step1 import codex

    execute = codex.execute

    def hanging_worker(command, **kwargs):
        return execute([sys.executable, "-c", "import time; time.sleep(10)"], **kwargs)

    monkeypatch.setattr(codex, "execute", hanging_worker)
    with pytest.raises(subprocess.TimeoutExpired):
        run_eval.run_rlm("test-model", "test", tmp_path, 0.1)
