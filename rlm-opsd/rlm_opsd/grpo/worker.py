"""Container entrypoint; inherits the official Worker, using stdio for subcalls.

Only this file and the pinned upstream worker are copied into task containers.
There are no inference credentials, host sockets, tests, or reference solutions.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import select
import signal
import sys
import threading
import time
import traceback

from upstream_worker import Worker

PROTOCOL_IN = os.fdopen(os.dup(0), "r", encoding="utf-8")
PROTOCOL_OUT = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)


class Output(io.TextIOBase):
    def __init__(self, limit=20_000):
        self.limit, self.total, self.parts = limit, 0, []
        self.lock = threading.Lock()

    def write(self, text):
        with self.lock:
            remaining = max(0, self.limit - self.total)
            if remaining:
                self.parts.append(text[:remaining])
            self.total += len(text)
        return len(text)

    def flush(self):
        pass

    def value(self):
        text = "".join(self.parts)
        if self.total > self.limit:
            text += f"\n[truncated: full output length {self.total} chars]"
        return text


def send(value):
    PROTOCOL_OUT.write(json.dumps(value, ensure_ascii=False) + "\n")
    PROTOCOL_OUT.flush()


@contextlib.contextmanager
def capture_fds(out, err):
    """Capture subprocess/os.write output without corrupting JSONL transport."""
    saved = [os.dup(fd) for fd in (0, 1, 2)]
    stop, threads = threading.Event(), []

    def drain(fd, target):
        try:
            while not stop.is_set():
                ready, _, _ = select.select([fd], [], [], 0.05)
                if ready:
                    chunk = os.read(fd, 8192)
                    if not chunk:
                        return
                    target.write(chunk.decode("utf-8", errors="replace"))
        finally:
            os.close(fd)

    try:
        with open(os.devnull, "rb") as null:
            os.dup2(null.fileno(), 0)
        for fd, target in ((1, out), (2, err)):
            reader, writer = os.pipe()
            os.dup2(writer, fd)
            os.close(writer)
            thread = threading.Thread(target=drain, args=(reader, target), daemon=True)
            threads.append(thread)
            thread.start()
        yield
    finally:
        for fd, original in enumerate(saved):
            os.dup2(original, fd)
            os.close(original)
        # Normal commands close their pipe writers and drain to EOF. Background
        # processes cannot keep a finished turn's observation capture alive.
        for thread in threads:
            thread.join(timeout=0.2)
        stop.set()
        for thread in threads:
            thread.join(timeout=0.2)


class ContainerWorker(Worker):
    def __init__(self):
        super().__init__(proxy_url="stdio", rollout_id="container", exec_timeout_s=120)
        self.namespace = {**self.globals, **self.locals}

    def _proxy_post(self, path, payload):
        # The Python execution budget excludes waiting for a child model. The
        # parent's rollout deadline still bounds the complete operation.
        alarm = signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            send(dict(type="subcall", path=path, payload=payload))
            raw = PROTOCOL_IN.readline()
            if not raw:
                raise RuntimeError("Parent disconnected during delegation")
            response = json.loads(raw)
            if response.get("type") != "subcall_result":
                raise RuntimeError("Unexpected delegation response")
            return response["result"]
        finally:
            signal.setitimer(signal.ITIMER_REAL, *alarm)

    def load_context(self, payload, index=None):
        index = super().load_context(payload, index)
        self.namespace.update(self.locals)
        return index

    def execute(self, code):
        out, err, start = Output(), Output(), time.monotonic()
        with capture_fds(out, err), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                self._exec_with_timeout(code, self.namespace)
            except BaseException:
                traceback.print_exc()
        # Preserve successful assignments even if a later statement raises.
        self.locals.update({k: v for k, v in self.namespace.items() if k not in self.globals})
        self._restore_scaffold()
        self.namespace.update(self.globals)
        self.namespace.update(self.locals)
        final = self._last_final_answer
        self._last_final_answer = None
        return dict(stdout=out.value(), stderr=err.value(), final_answer=final,
                    execution_time=time.monotonic() - start,
                    locals_keys=[k for k in self.locals if not k.startswith("_")])


def main():
    # A remote process group lets the parent terminate commands spawned by a
    # cancelled worker; killing only the local `docker exec` client is insufficient.
    try:
        os.setsid()
    except PermissionError:
        if os.getpgrp() != os.getpid():
            raise
    worker = ContainerWorker()
    send(dict(id="_init", ok=True, pid=os.getpid()))
    for raw in PROTOCOL_IN:
        request = json.loads(raw)
        request_id = request["id"]
        try:
            kind = request["type"]
            if kind == "shutdown":
                send(dict(id=request_id, ok=True))
                return
            if kind == "load_context":
                result = dict(index=worker.load_context(request["payload"], request.get("index")))
            elif kind == "exec":
                worker.exec_timeout_s = float(request.get("timeout", 120))
                result = worker.execute(request["code"])
            elif kind == "finish":
                # OPSD FINAL_VAR compatibility; resolve a name, never eval model text.
                name = request.get("variable")
                if name is not None:
                    if not name.isidentifier() or name not in worker.namespace:
                        raise ValueError(f"FINAL_VAR requires an existing variable: {name!r}")
                    value = worker.namespace[name]
                else:
                    value = request["value"]
                result = dict(final_answer=str(value))
            else:
                raise ValueError(f"Unknown request: {kind}")
            send(dict(id=request_id, ok=True, **result))
        except BaseException as exc:
            send(dict(id=request_id, ok=False, error=f"{type(exc).__name__}: {exc}"))


if __name__ == "__main__":
    main()
