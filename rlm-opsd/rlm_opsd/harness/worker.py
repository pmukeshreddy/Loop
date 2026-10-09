"""Resource-limited variant of the pinned rlm_train.worker.Worker protocol."""
import contextlib
import json
import math
import resource
import sys
import time
import traceback

import psutil
from rlm_train.worker import Worker


class Capture:
    def __init__(self, limit):
        self.limit = limit
        self.parts = []
        self.kept = self.total = self.stderr_total = 0

    def write(self, value):
        self.total += len(value)
        part = value[:max(0, self.limit - self.kept)]
        if part:
            self.parts.append(part)
            self.kept += len(part)
        return len(value)

    def flush(self):
        pass


class StderrCapture:
    def __init__(self, capture):
        self.capture = capture

    def write(self, value):
        self.capture.stderr_total += len(value)
        return self.capture.write(value)

    def flush(self):
        pass


class HarnessWorker(Worker):
    def __init__(self, *, settings, **kwargs):
        self.settings = settings
        super().__init__(exec_timeout_s=0, **kwargs)
        # One namespace, including function globals, persists after exceptions.
        self.namespace = {**self.globals, **self.locals}
        self.namespace["answer"] = {}
        self.namespace.pop("rlm_query", None)
        self.namespace.pop("rlm_query_batched", None)
        if settings["enable_recursion"]:
            self.namespace["rlm_query"] = self._rlm_query

    def load_context(self, payload, index=None):
        index = super().load_context(payload, index)
        self.namespace.update(self.locals)
        self.namespace["answer"] = {}
        return index

    def _rlm_query(self, prompt):
        if not isinstance(prompt, str):
            raise TypeError("rlm_query expects a str")
        result = self._proxy_post("llm_query", dict(prompt=prompt, recursive=True))
        return f"Error: {result['error']}" if result.get("error") else result.get("response", "")

    def _llm_query(self, prompt, model=None):
        if not isinstance(prompt, str):
            raise TypeError("llm_query expects a str")
        return super()._llm_query(prompt, model)

    def _llm_query_batched(self, prompts, model=None):
        if not isinstance(prompts, list) or not all(isinstance(p, str) for p in prompts):
            raise TypeError("llm_query_batched expects list[str]")
        return super()._llm_query_batched(prompts, model)

    def execute(self, code):
        capture = Capture(self.settings["stdout_max_chars"])
        error = None
        start = time.perf_counter()
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(StderrCapture(capture)):
            try:
                self._exec_with_timeout(code, self.namespace)
            except BaseException as exc:
                error = type(exc).__name__
                traceback.print_exc()
        return dict(stdout="".join(capture.parts), stderr="", error=error,
                    stdout_raw_chars=capture.total, stderr_raw_chars=capture.stderr_total,
                    final_answer=None, execution_time=time.perf_counter() - start,
                    locals_keys=[])


def main():
    settings = json.loads(sys.argv[1])
    worker = HarnessWorker(settings=settings, proxy_url=sys.argv[2], rollout_id=sys.argv[3],
                           depth=int(sys.argv[4]))
    limits = settings["sandbox"]
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_limit = math.ceil(cpu.ru_utime + cpu.ru_stime + limits["cpu_time_s"])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
    if sys.platform == "linux":
        # Libraries reserve virtual mappings at import. Bound additional address
        # space; the parent's RSS watchdog enforces the configured memory limit.
        address_limit = psutil.Process().memory_info().vms + limits["memory_mb"] * 1024**2
        resource.setrlimit(resource.RLIMIT_AS, (address_limit, address_limit))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    protocol = sys.stdout

    def send(value):
        protocol.write(json.dumps(value, ensure_ascii=False) + "\n")
        protocol.flush()

    send(dict(id="_init", ok=True))
    for line in sys.stdin:
        request = json.loads(line)
        kind, rid = request["type"], request["id"]
        try:
            if kind == "load_context":
                result = dict(index=worker.load_context(request["payload"], request.get("index")))
            elif kind == "exec":
                result = worker.execute(request["code"])
            elif kind == "resolve":
                name = request["name"]
                if not name.isidentifier() or name not in worker.namespace:
                    result = dict(found=False, value="")
                else:
                    # A __str__ may execute arbitrary Python too; parent watchdogs
                    # apply to resolution, and printed text cannot corrupt JSONL.
                    with contextlib.redirect_stdout(Capture(0)), contextlib.redirect_stderr(Capture(0)):
                        result = dict(found=True, value=str(worker.namespace[name]))
            elif kind == "shutdown":
                send(dict(id=rid, ok=True))
                return
            else:
                raise ValueError(f"unknown request type: {kind}")
            send(dict(id=rid, ok=True, **result))
        except BaseException as exc:
            send(dict(id=rid, ok=False, error=f"{type(exc).__name__}: {exc}"))


if __name__ == "__main__":
    main()
