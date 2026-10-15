"""One Docker checkout per rollout; pristine, inaccessible-to-policy grading."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from rlm_train.repl.base import ExecResult
from rlm_train.repl.subprocess import SubprocessReplBackend

from .tasks import RepoTask, image_tag


class InfrastructureError(RuntimeError):
    """An unavailable container/grader is not evidence of a wrong solution."""


async def docker(*args, timeout=120, check=True, input=None):
    process = await asyncio.create_subprocess_exec(
        "docker", *map(str, args), stdin=asyncio.subprocess.PIPE if input is not None else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(process.communicate(input), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if check and process.returncode:
        raise InfrastructureError(f"docker {args[0]} failed ({process.returncode}): "
                                  + err.decode(errors="replace")[-4000:])
    return process.returncode, out, err


async def prepare_image(task: RepoTask):
    image = task.image or image_tag(task)
    code, _, _ = await docker("image", "inspect", image, check=False)
    if code:
        if task.image:
            await docker("pull", image, timeout=task.build_timeout)
        else:
            # The build context contains only environment/, never solution/ or tests/.
            await docker("build", "-t", image, task.directory / "environment",
                         timeout=task.build_timeout)
    return image


class TaskRuntime:
    def __init__(self, task: RepoTask, artifact_dir: Path, *, max_patch_bytes=16 * 1024 * 1024):
        self.task, self.artifact_dir = task, artifact_dir
        self.max_patch_bytes = max_patch_bytes
        self.container = f"loop-grpo-{uuid.uuid4().hex}"
        self.image = task.image or image_tag(task)
        self.backends = set()
        self.grade_containers = set()

    async def create(self, name, *, verifier=False):
        env = {**self.task.environment, **(self.task.verifier_environment if verifier else {})}
        options = [part for key, value in env.items() for part in ("--env", f"{key}={value}")]
        await docker("run", "-d", "--name", name, "--network", "none", "--user", "0",
                     "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                     "--pids-limit", "512", "--memory", f"{self.task.memory_mb}m",
                     "--cpus", str(self.task.cpus), *options, "--entrypoint", "/bin/sh",
                     self.image, "-c", "while :; do sleep 3600; done", timeout=300)

    async def start(self):
        self.artifact_dir.mkdir(parents=True, exist_ok=False)
        try:
            self.image = await prepare_image(self.task)
            await self.create(self.container)
            await self.exec("git", "config", "--global", "--add", "safe.directory", self.task.repo_path)
            await self.exec("git", "checkout", "--detach", self.task.base_commit)
            _, head, _ = await self.exec("git", "rev-parse", "HEAD")
            if head.decode().strip() != self.task.base_commit:
                raise InfrastructureError("Task container did not check out base_commit")
            _, shallow, _ = await self.exec("git", "rev-parse", "--is-shallow-repository")
            if shallow.decode().strip() != "false":
                raise InfrastructureError("Task image must contain full Git history through base_commit")
            # Copy only the stdlib-only official worker and its transport adapter.
            spec = importlib.util.find_spec("rlm_train.worker")
            if spec is None or spec.origin is None:
                raise InfrastructureError("Pinned rlm_train.worker is not installed")
            with tempfile.TemporaryDirectory(prefix="loop-grpo-worker-") as tmp:
                directory = Path(tmp) / "loop-rlm"
                directory.mkdir()
                shutil.copyfile(spec.origin, directory / "upstream_worker.py")
                shutil.copyfile(Path(__file__).with_name("worker.py"), directory / "worker.py")
                await docker("exec", self.container, "mkdir", "-p", "/opt/loop-rlm")
                await docker("cp", str(directory) + "/.", f"{self.container}:/opt/loop-rlm")
        except BaseException:
            await self.close()
            raise

    async def exec(self, *command, timeout=120, input=None):
        return await docker("exec", *( ["-i"] if input is not None else []),
                            "-w", self.task.repo_path, self.container, *command,
                            timeout=timeout, input=input)

    async def snapshot(self) -> Path:
        # A private index includes committed, staged, unstaged, deleted and new
        # non-ignored files without rewriting the model's own index or commits.
        index = f"/tmp/loop-index-{uuid.uuid4().hex}"
        script = ('set -eu\nexport GIT_INDEX_FILE="$1"\n'
                  'trap \'rm -f "$GIT_INDEX_FILE" "$GIT_INDEX_FILE.lock"\' EXIT\n'
                  'git read-tree "$2"\ngit add -A -- .\n'
                  'git diff --cached --binary --no-ext-diff "$2" --\n')
        _, patch, _ = await self.exec("/bin/sh", "-c", script, "snapshot", index, self.task.base_commit)
        if len(patch) > self.max_patch_bytes:
            raise ValueError("Submitted patch exceeds max_patch_bytes")
        target = self.artifact_dir / "model.patch"
        target.write_bytes(patch)
        return target

    async def grade(self, patch: Path) -> dict:
        name = f"loop-grade-{uuid.uuid4().hex}"
        self.grade_containers.add(name)
        verifier_dir = self.artifact_dir / "verifier"
        verifier_dir.mkdir()
        try:
            await self.create(name, verifier=True)
            await docker("exec", name, "mkdir", "-p", "/logs/artifacts", "/logs/verifier", "/tests")
            await docker("cp", str(self.task.directory / "tests") + "/.", f"{name}:/tests")
            await docker("cp", patch, f"{name}:/logs/artifacts/model.patch")
            # The task's grader applies model.patch and then its held-out test.patch.
            # Never reset/clean this pristine image: it can contain fixture assets.
            try:
                code, out, err = await docker("exec", name, "bash", "/tests/test.sh",
                                               timeout=self.task.verifier_timeout, check=False)
            except TimeoutError as exc:
                raise InfrastructureError("Verifier timed out; no correctness label") from exc
            (verifier_dir / "test-stdout.txt").write_bytes(out + err)
            await docker("cp", f"{name}:/logs/verifier/.", verifier_dir)
            reward_path = verifier_dir / "reward.json"
            if code != 0 or not reward_path.is_file():
                raise InfrastructureError(f"Verifier failed (exit {code}) or omitted reward.json")
            try:
                result = json.loads(reward_path.read_text())
            except (ValueError, OSError) as exc:
                raise InfrastructureError("Malformed verifier reward.json") from exc
            if not isinstance(result, dict) or result.get("reward") not in (0, 1):
                raise InfrastructureError("Verifier must emit binary reward 0 or 1")
            # Where DeepSWE supplies counts, require every required test to pass.
            if result["reward"] == 1:
                for bucket in ("f2p", "p2p"):
                    total, passed = result.get(f"{bucket}_total"), result.get(f"{bucket}_passed")
                    if total is not None and (passed != total or (bucket == "f2p" and total <= 0)):
                        raise InfrastructureError("Verifier reward contradicts required-test counts")
            return result
        finally:
            await docker("rm", "-f", name, check=False)
            self.grade_containers.discard(name)

    async def close(self):
        # Remove the container first: this kills children spawned by generated code.
        try:
            await docker("rm", "-f", self.container, *self.grade_containers, check=False)
        finally:
            await asyncio.gather(*(backend.stop() for backend in list(self.backends)), return_exceptions=True)
            self.backends.clear()
            self.grade_containers.clear()


class DockerReplBackend(SubprocessReplBackend):
    """Official JSONL REPL transport with Docker execution and parent subcall relay."""
    def __init__(self, runtime: TaskRuntime, delegate, *, request_timeout=900, exec_timeout=120):
        super().__init__(request_timeout=request_timeout)
        self.runtime, self.delegate, self.exec_timeout = runtime, delegate, exec_timeout
        self._remote_pid = None
        self._closing = False

    async def start(self, proxy_url="", rollout_id="", depth=1):
        self._proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "-w", self.runtime.task.repo_path,
            self.runtime.container, "python3", "-u", "/opt/loop-rlm/worker.py",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, limit=self._STREAM_LIMIT)
        self.runtime.backends.add(self)
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            result = await asyncio.wait_for(self._read_line(), self._startup_timeout)
            if not result.get("ok"):
                raise InfrastructureError("Container REPL failed to initialize")
            self._remote_pid = int(result["pid"])
        except BaseException:
            await self.stop()
            raise

    async def _read_line(self):
        while True:
            response = await super()._read_line()
            if response.get("type") != "subcall":
                return response
            try:
                result = (dict(error="Worker is closing") if self._closing else
                          await self.delegate(response["path"], response["payload"]))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                result = dict(error=f"{type(exc).__name__}: {exc}")
            await self._send(dict(type="subcall_result", result=result))

    async def execute(self, code):
        result = await self._request(dict(type="exec", code=code, timeout=self.exec_timeout))
        return ExecResult(**{key: result[key] for key in (
            "stdout", "stderr", "final_answer", "execution_time", "locals_keys")})

    async def finish(self, *, variable=None, value=""):
        return await self._request(dict(type="finish", variable=variable, value=value))

    async def stop(self):
        self._closing = True
        try:
            await self._kill_worker()
        finally:
            try:
                await super().stop()
            finally:
                self.runtime.backends.discard(self)

    async def _kill_worker(self):
        if self._remote_pid is not None:
            await docker("exec", self.runtime.container, "python3", "-c",
                         "import os,signal,sys; os.killpg(int(sys.argv[1]), signal.SIGKILL)",
                         str(self._remote_pid), check=False, timeout=15)
            self._remote_pid = None
        await super()._kill_worker()
