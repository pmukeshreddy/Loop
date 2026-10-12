import sys

sys.dont_write_bytecode = True

import json
from contextvars import Context
from types import SimpleNamespace

from structlog._frames import _find_first_app_frame_and_name


def make_chain(specs):
    frames = {}
    back = None
    for label, module_name in reversed(specs):
        frame = SimpleNamespace(
            f_globals={} if module_name is None else {"__name__": module_name},
            f_back=back,
        )
        frames[label] = frame
        back = frame
    return back, frames


def evaluate(head, frames, stacklevel):
    # A fresh context leaves _ASYNC_CALLING_STACK unset.
    frame, module_name = Context().run(
        _find_first_app_frame_and_name,
        additional_ignores=["shim", "logging"],
        stacklevel=stacklevel,
        _getframe=lambda: head,
    )
    label = next(label for label, candidate in frames.items() if candidate is frame)
    return [label, module_name]


head, frames = make_chain(
    [
        ("A", "structlog._base"),
        ("B", "shim.wrap"),
        ("C", "application.view"),
        ("D", "logging"),
        ("E", None),
        ("F", "cli.main"),
    ]
)

answer = {
    key: evaluate(head, frames, stacklevel)
    for key, stacklevel in [
        ("none", None),
        ("zero", 0),
        ("one", 1),
        ("two", 2),
        ("nine", 9),
    ]
}

exhausted_head, exhausted_frames = make_chain(
    [("X", "structlog.runner"), ("Y", "shim.hidden")]
)
answer["exhausted"] = evaluate(exhausted_head, exhausted_frames, None)

print(json.dumps({"answer": answer}))