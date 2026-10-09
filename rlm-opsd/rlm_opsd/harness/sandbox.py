import asyncio
import contextlib
import os
from pathlib import Path
import signal
import sys
import tempfile

import psutil
from rlm_train.repl.base import ExecResult
from rlm_train.repl.subprocess import SubprocessReplBackend, WorkerProtocolError


class SandboxLimit(RuntimeError):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(f"sandbox {kind} limit exceeded; worker terminated")


class SandboxBackend(SubprocessReplBackend):
    """Pinned JSONL transport with process-group cleanup and parent watchdogs."""
    def __init__(self, config):
        super().__init__(worker_module="rlm_opsd.harness.worker",
                         request_timeout=config.sandbox.wall_time_s)
        self.config = config
        self.last_details = {}
        self._limit_hit = None
        self._monitor = None
        self._temp = None
        self._returncode = None
        self._group_killed = False

    @property
    def process_returncode(self):
        return self._proc.returncode if self._proc else self._returncode

    async def start(self, proxy_url, rollout_id, depth=1):
        self._group_killed = False
        self._limit_hit = None
        self._returncode = None
        self._temp = tempfile.TemporaryDirectory(prefix="rlm-opsd-")
        # Do not pass API keys or other parent credentials to generated Python.
        env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT") if key in os.environ}
        env["PYTHONPATH"] = os.pathsep.join(str(Path(p or ".").resolve()) for p in sys.path)
        env["PYTHONUNBUFFERED"] = "1"
        self._proc = await asyncio.create_subprocess_exec(
            self._python, "-u", "-m", self._worker_module, self.config.model_dump_json(),
            proxy_url, rollout_id, str(depth), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=env, cwd=self._temp.name, start_new_session=True, limit=self._STREAM_LIMIT)
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            init = await asyncio.wait_for(self._read_line(), self._startup_timeout)
            if not init.get("ok"):
                raise WorkerProtocolError(str(init))
            proc = psutil.Process(self._proc.pid)
            times = proc.cpu_times()
            self._cpu_baseline = times.user + times.system
            self._monitor = asyncio.create_task(self._watch_resources(proc))
        except BaseException:
            await self.stop()
            raise

    async def _watch_resources(self, process):
        # Retain the maximum observed CPU for exited children as well.
        used = {}
        while self._proc and self._proc.returncode is None:
            try:
                rss = 0
                for proc in [process, *process.children(recursive=True)]:
                    try:
                        rss += proc.memory_info().rss
                        times = proc.cpu_times()
                        used[(proc.pid, proc.create_time())] = times.user + times.system
                    except psutil.NoSuchProcess:
                        continue
                if rss > self.config.sandbox.memory_mb * 1024**2:
                    self._limit_hit = "memory"
                elif sum(used.values()) - self._cpu_baseline > self.config.sandbox.cpu_time_s:
                    self._limit_hit = "cpu_time"
                if self._limit_hit:
                    await self._kill_worker()
                    return
            except psutil.NoSuchProcess:
                return
            await asyncio.sleep(0.02)

    async def _kill_worker(self):
        if self._proc is not None:
            # Signal once, including when only descendants remain. A second
            # teardown must not signal a process group whose ID may be reused.
            if not self._group_killed:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self._proc.pid, signal.SIGKILL)
                self._group_killed = True
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._proc.wait(), 2)

    async def _request(self, payload):
        try:
            return await super()._request(payload)
        except asyncio.CancelledError:
            await self._kill_worker()
            raise
        except (WorkerProtocolError, BrokenPipeError, ConnectionResetError) as exc:
            if self._limit_hit:
                # Pipe EOF can precede the watchdog's completed wait/reap.
                await self._kill_worker()
                raise SandboxLimit(self._limit_hit) from exc
            if "parent watchdog" in str(exc):
                self._limit_hit = "wall_time"
                raise SandboxLimit("wall_time") from exc
            if self._proc and self._proc.returncode == -signal.SIGXCPU:
                raise SandboxLimit("cpu_time") from exc
            raise

    async def execute(self, code):
        result = await self._request(dict(type="exec", code=code))
        self.last_details = result
        if result.get("error") == "MemoryError":
            self._limit_hit = "memory"
            await self._kill_worker()
            raise SandboxLimit("memory")
        return ExecResult(stdout=result["stdout"], stderr=result["stderr"],
                          execution_time=result["execution_time"])

    async def resolve(self, name):
        return await self._request(dict(type="resolve", name=name))

    async def stop(self):
        if self._monitor:
            self._monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor
            self._monitor = None
        await self._kill_worker()
        if self._proc:
            self._returncode = self._proc.returncode
        await super().stop()
        if self._temp:
            self._temp.cleanup()
            self._temp = None
