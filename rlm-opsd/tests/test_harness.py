"""M1 contract tests: real workers and deterministic model transports, no GPU."""
import asyncio
import json
from pathlib import Path

import pytest


def config(**changes):
    from rlm_opsd.harness import HarnessConfig

    values = dict(max_turns=4, max_tokens_per_turn=128, max_subcalls=4,
                  max_subcall_chars=100, subcall_concurrency=2, prefix_chars=4,
                  stdout_max_chars=128, sandbox=dict(wall_time_s=8, memory_mb=768,
                                                    cpu_time_s=5))
    values.update(changes)
    return HarnessConfig.model_validate(values)


class FrozenClient:
    """Deterministic transport; the actual worker reaches it over the RLM proxy."""
    def __init__(self):
        self.requests = []
        self.active = 0
        self.peak = 0

    async def get_response(self, **request):
        from verifiers.types import Response, ResponseMessage

        self.requests.append(request)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.03)
            return Response(id="fixture", created=0, model=request["model"], message=ResponseMessage(
                content="leaf:" + request["prompt"][0].content, finish_reason="stop", is_truncated=False))
        finally:
            self.active -= 1


def episode(tmp_path, *, cfg=None, client=None, context="abcdefSECRET", **kwargs):
    from rlm_opsd.harness import Episode

    return Episode(config=cfg or config(), frozen_client=client or FrozenClient(),
                   frozen_model="initial-weights", log_dir=tmp_path,
                   info=dict(task_id="../task", family="fixture", domain="test",
                             tags=["long_context"], context=context, query="Find it"),
                   **kwargs)


@pytest.mark.parametrize("context,expected", [
    ("abcdSECRET", dict(context_type="str", context_total_length=10,
                        context_lengths=[], context_prefix="abcd")),
    (["a", "bc", "defSECRET"], dict(context_type="list", context_total_length=12,
                                    context_lengths=[1, 2, 9], context_prefix="abcd")),
    ([], dict(context_type="list", context_total_length=0, context_lengths=[], context_prefix="")),
])
def test_metadata(context, expected):
    from rlm_opsd.harness import context_metadata

    assert context_metadata(context, 4) == expected
    assert context_metadata(context, 0)["context_prefix"] == ""


@pytest.mark.parametrize("invalid", [None, ["a", 1], {"secret": "a"}])
def test_context_type_validation(invalid):
    from rlm_opsd.harness import context_metadata

    with pytest.raises((ValueError, TypeError)):
        context_metadata(invalid, 4)


def test_config_loads_and_rejects_invalid_budgets():
    from rlm_opsd.harness import HarnessConfig

    cfg = HarnessConfig.from_yaml("configs/harness.yaml")
    assert cfg.max_turns > 0 and not cfg.enable_recursion and cfg.max_depth == 1
    for change in [dict(max_turns=0), dict(max_subcalls=-1), dict(subcall_concurrency=0),
                   dict(prefix_chars=-1), dict(max_tokens_per_turn=0), dict(unknown=1),
                   dict(sandbox=dict(wall_time_s=0, memory_mb=0, cpu_time_s=0)),
                   dict(enable_recursion=False, max_depth=2)]:
        with pytest.raises(ValueError):
            config(**change)


def test_finish_parser_ignores_all_fences_and_after_finish_code():
    from rlm_opsd.harness import parse_turn

    text = '```python\nFINAL(wrong)\n```\n~~~text\nFINAL(wrong2)\n~~~\n'
    text += '```repl\nx = "FINAL(wrong3)"\n```\nFINAL(a (nested) answer)\nignored\n```repl\nx = 99\n```'
    parsed = parse_turn(text)
    assert parsed.code_blocks == ['x = "FINAL(wrong3)"']
    assert parsed.finish_type == "FINAL" and parsed.finish_argument == "a (nested) answer"
    assert parsed.ignored_after_finish == '\nignored\n```repl\nx = 99\n```'
    assert parse_turn('```repl\nprint("FINAL(x)")').finish_type is None
    assert parse_turn('notFINAL(no)').finish_type is None


def test_persistence_metadata_errors_and_final_variable(tmp_path):
    async def run():
        async with episode(tmp_path) as ep:
            first_prompt = json.dumps(ep.messages)
            assert "SECRET" not in first_prompt and "abcd" in first_prompt
            out = await ep.accept('```repl\nx = len(context)\nprint(x)\n```', [101, 102])
            assert out == "12\n"
            out = await ep.accept("FINAL_VAR(missing)", [103])
            assert "protocol-error" in out and not ep.done
            assert ep.trace.turns[1].finish_error
            out = await ep.accept('```repl\nx += 1\nprint(1 / 0)\n```', [104])
            assert "ZeroDivisionError" in out or ep.trace.turns[-1].error == "ZeroDivisionError"
            await ep.accept("FINAL_VAR(x)\nDo not execute\n```repl\nx = 0\n```", [105, 106])
            assert ep.done and ep.trace.final.value == "13"
            assert ep.trace.turns[-1].code_blocks == []
            assert not ep.trace.budget_hits["max_turns"]
        logs = list(tmp_path.glob("*.json"))
        assert len(logs) == 1
        raw = json.loads(logs[0].read_text())
        assert raw["task_id"] == "../task" and raw["manual_version"] == "manual_v1"
        assert raw["prompt_variant"] == "student"
        assert raw["turns"][0]["assistant_token_ids"] == [101, 102]
        assert raw["turns"][0]["stdout_raw_chars"] == 3
        assert raw["final"] == dict(type="FINAL_VAR", value="13", error=None)
        assert raw["timings"]["episode_s"] > 0
        from rlm_opsd.harness import EpisodeTrace
        EpisodeTrace.model_validate(raw)
    asyncio.run(run())


def test_output_is_bounded_and_counts_full_length_across_blocks(tmp_path):
    async def run():
        async with episode(tmp_path, cfg=config(stdout_max_chars=32)) as ep:
            out = await ep.accept('```repl\nprint("α" * 10000, end="")\n```\n```repl\nprint("z" * 20)\n```', [])
            assert out == "α" * 32 + "\n[truncated: full output length 10021 chars]"
            assert ep.trace.turns[0].stdout_raw_chars == 10021
            assert ep.trace.turns[0].stdout_truncated == out
    asyncio.run(run())


def test_stderr_and_traceback_are_returned(tmp_path):
    async def run():
        async with episode(tmp_path, cfg=config(stdout_max_chars=2000)) as ep:
            out = await ep.accept('```repl\nimport sys\nprint("err", file=sys.stderr)\nraise ValueError("bad")\n```', [])
            assert "err\n" in out and "Traceback" in out and "ValueError: bad" in out
            assert ep.trace.turns[0].stderr_raw_chars > 0
    asyncio.run(run())


def test_final_on_last_turn_and_upstream_answer_dict_cannot_finish(tmp_path):
    async def run():
        async with episode(tmp_path, cfg=config(max_turns=2)) as ep:
            await ep.accept('```repl\nanswer = {"content": "wrong", "ready": True}\n```', [])
            assert not ep.done
            await ep.accept("FINAL(done)", [])
            assert ep.trace.final.value == "done" and not ep.trace.budget_hits["max_turns"]
        async with episode(tmp_path, cfg=config(max_turns=1)) as ep:
            await ep.accept('```repl\nprint("last turn executed")\n```', [])
            assert ep.done and ep.trace.budget_hits["max_turns"]
            assert "last turn executed" in ep.trace.turns[0].stdout_truncated
            with pytest.raises(RuntimeError, match="finished"):
                await ep.accept("FINAL(too late)", [])
        assert len(list(tmp_path.glob("*.json"))) == 2
    asyncio.run(run())


def test_subcall_budget_concurrency_routing_and_logs(tmp_path):
    async def run():
        client = FrozenClient()
        cfg = config(max_subcalls=3, max_subcall_chars=10, subcall_concurrency=2)
        async with episode(tmp_path, cfg=cfg, client=client) as ep:
            await ep.accept('```repl\nprint(llm_query("x" * 11))\n```', [])
            out = await ep.accept('```repl\nprint(llm_query_batched(["a", "b", "c", "d"]))\n```', [])
            assert len(client.requests) == 3 and client.peak == 2
            assert all(r["model"] == "initial-weights" for r in client.requests)
            assert ep.trace.budget_hits["max_subcalls"] and ep.trace.budget_hits["max_subcall_chars"]
            calls = ep.trace.turns[1].subcalls
            assert len(calls) == 4 and all(c.turn_index == 1 for c in calls)
            assert sum(c.error is None for c in calls) == 3
            assert all(c.latency_s >= 0 and c.prompt_chars == 1 for c in calls)
            assert [c.output_chars for c in calls if c.error is None] == [6, 6, 6]
            assert "max_subcalls" in out
    asyncio.run(run())


def test_recursion_is_absent_by_default(tmp_path):
    async def run():
        async with episode(tmp_path) as ep:
            out = await ep.accept('```repl\nrlm_query("question")\n```', [])
            assert ep.trace.turns[0].error == "NameError"
    asyncio.run(run())


@pytest.mark.parametrize("kind,code,limits", [
    ("wall_time", 'import time\ntime.sleep(10)', dict(wall_time_s=0.3, memory_mb=768, cpu_time_s=5)),
    ("cpu_time", 'while True: pass', dict(wall_time_s=8, memory_mb=768, cpu_time_s=0.3)),
    ("memory", 'import time\nx = bytearray(300 * 1024 * 1024)\ntime.sleep(5)',
     dict(wall_time_s=8, memory_mb=256, cpu_time_s=5)),
])
def test_real_worker_resource_limits(tmp_path, kind, code, limits):
    async def run():
        async with episode(tmp_path, cfg=config(sandbox=limits)) as ep:
            out = await ep.accept(f"```repl\n{code}\n```", [])
            assert ep.done and ep.trace.budget_hits[kind]
            assert kind in out and ep.trace.final.error
            assert ep.backend.process_returncode is not None
    asyncio.run(run())


def test_worker_group_cleanup_is_idempotent_after_success(monkeypatch):
    from types import SimpleNamespace
    from rlm_opsd.harness.sandbox import SandboxBackend

    backend = SandboxBackend(config())
    signals = []

    async def wait():
        backend._proc.returncode = -9
        return -9

    backend._proc = SimpleNamespace(pid=12345, returncode=None, wait=wait)

    def killpg(pid, sig):
        signals.append((pid, sig))
        if len(signals) > 1:
            # A removed/reused process group need not still belong to us.
            raise PermissionError("process group no longer owned")

    monkeypatch.setattr("rlm_opsd.harness.sandbox.os.killpg", killpg)

    async def run():
        await backend._kill_worker()
        await backend._kill_worker()
        assert backend.process_returncode == -9
        assert len(signals) == 1

    asyncio.run(run())


def test_resource_limit_waits_for_worker_exit_before_raising(monkeypatch):
    from types import SimpleNamespace
    from rlm_opsd.harness.sandbox import SandboxBackend, SandboxLimit
    from rlm_train.repl.subprocess import SubprocessReplBackend, WorkerProtocolError

    backend = SandboxBackend(config())
    backend._limit_hit = "cpu_time"

    async def wait():
        await asyncio.sleep(0)
        backend._proc.returncode = -9
        return -9

    async def closed_pipe(self, payload):
        # EOF may arrive before asyncio updates the child's return code.
        raise WorkerProtocolError("worker closed stdout")

    backend._proc = SimpleNamespace(pid=12345, returncode=None, wait=wait)
    monkeypatch.setattr(SubprocessReplBackend, "_request", closed_pipe)
    monkeypatch.setattr("rlm_opsd.harness.sandbox.os.killpg", lambda pid, sig: None)

    async def run():
        with pytest.raises(SandboxLimit, match="cpu_time"):
            await backend.execute("while True: pass")
        assert backend.process_returncode == -9

    asyncio.run(run())


def test_worker_cleanup_does_not_hide_initial_permission_failure(monkeypatch):
    from types import SimpleNamespace
    from rlm_opsd.harness.sandbox import SandboxBackend

    backend = SandboxBackend(config())
    backend._proc = SimpleNamespace(pid=12345, returncode=None)

    def denied(pid, sig):
        raise PermissionError("cannot terminate worker group")

    monkeypatch.setattr("rlm_opsd.harness.sandbox.os.killpg", denied)
    with pytest.raises(PermissionError, match="cannot terminate"):
        asyncio.run(backend._kill_worker())


def test_cancelled_episode_is_logged_and_worker_stopped(tmp_path):
    async def run():
        ep = episode(tmp_path)
        with pytest.raises(asyncio.CancelledError):
            async with ep:
                task = asyncio.create_task(ep.accept('```repl\nimport time\ntime.sleep(20)\n```', []))
                await asyncio.sleep(0.2)
                task.cancel()
                await task
        assert ep.backend.process_returncode is not None
        raw = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert "cancel" in raw["final"]["error"].lower()
    asyncio.run(run())


def test_subcall_timeout_is_logged_and_worker_can_continue(tmp_path):
    class SlowClient:
        async def get_response(self, **request):
            await asyncio.sleep(10)

    async def run():
        async with episode(tmp_path, cfg=config(subcall_timeout_s=0.05), client=SlowClient()) as ep:
            out = await ep.accept('```repl\nprint(llm_query("test"))\n```', [])
            assert "TimeoutError" in out
            assert "TimeoutError" in ep.trace.turns[0].subcalls[0].error
            await ep.accept("FINAL(recovered)", [])
            assert ep.trace.final.value == "recovered"
    asyncio.run(run())


def test_enabled_recursion_uses_child_repl_and_honors_depth(tmp_path):
    class RecursiveClient:
        async def get_response(self, **request):
            from verifiers.types import Response, ResponseMessage
            return Response(id="recursive", created=0, model=request["model"], message=ResponseMessage(
                content='```repl\nprint(rlm_query("too deep"))\nanswer = len(context)\n```\nFINAL_VAR(answer)',
                finish_reason="stop", is_truncated=False))

    async def run():
        cfg = config(enable_recursion=True, max_depth=2)
        async with episode(tmp_path, cfg=cfg, client=RecursiveClient()) as ep:
            out = await ep.accept('```repl\nvalue = rlm_query("12345")\nprint(value)\n```\nFINAL_VAR(value)', [])
            assert out == "5\n" and ep.trace.final.value == "5"
            assert ep.trace.budget_hits["max_depth"]
            assert ep.trace.turns[0].subcalls[0].kind == "rlm_query"
        logs = [json.loads(path.read_text()) for path in tmp_path.glob("*.json")]
        assert len(logs) == 2
        child = next(log for log in logs if log["task_id"].endswith("/recursive"))
        assert "max_depth" in child["turns"][0]["stdout_truncated"]
    asyncio.run(run())


def test_code_globals_and_deletions_persist(tmp_path):
    async def run():
        async with episode(tmp_path) as ep:
            await ep.accept('```repl\nn = 1\ndef value():\n    return n\n```', [])
            out = await ep.accept('```repl\nn = 9\nprint(value())\ndel n\n```', [])
            assert out == "9\n"
            out = await ep.accept('FINAL_VAR(n)', [])
            assert "protocol-error" in out and not ep.done
    asyncio.run(run())


def test_wall_watchdog_kills_worker_child_process(tmp_path):
    async def run():
        import psutil
        marker = tmp_path / "child-pid"
        code = ('import subprocess, sys, time\n'
                'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])\n'
                f'open({str(marker)!r}, "w").write(str(child.pid))\n'
                'time.sleep(20)')
        async with episode(tmp_path, cfg=config(sandbox=dict(wall_time_s=0.5, memory_mb=768, cpu_time_s=5))) as ep:
            await ep.accept(f"```repl\n{code}\n```", [])
            assert ep.trace.budget_hits["wall_time"]
        pid = int(marker.read_text())
        if psutil.pid_exists(pid):
            assert psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    asyncio.run(run())


@pytest.mark.parametrize("text,kind,value,error", [
    ('FINAL_VAR(x)', "FINAL_VAR", "x", False),
    ('FINAL({"a": "parenthesis )"})', "FINAL", '{"a": "parenthesis )"}', False),
    ("FINAL(it's done)", "FINAL", "it's done", False),
    ('FINAL(unfinished', None, "", True),
    ('````repl\nprint("``` and FINAL(no)")\n````\nFINAL(yes)', "FINAL", "yes", False),
])
def test_finish_protocol_cases(text, kind, value, error):
    from rlm_opsd.harness import parse_turn
    result = parse_turn(text)
    assert result.finish_type == kind and result.finish_argument == value
    assert bool(result.finish_error) == error
