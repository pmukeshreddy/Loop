import sys

sys.dont_write_bytecode = True

import contextlib
import inspect
import io
import json

from marshmallow import fields


def compute_answer():
    classes = set()
    for name in fields.__all__:
        obj = getattr(fields, name)
        if (
            inspect.isclass(obj)
            and obj.__module__ == fields.__name__
            and issubclass(obj, fields.Field)
            and obj is not fields.Field
            and not inspect.isabstract(obj)
        ):
            classes.add(obj)

    matches = []
    for cls in sorted(classes, key=lambda candidate: candidate.__name__):
        accepts_both = True
        for value in (True, False):
            try:
                # Construct a fresh instance for each input, without binding it.
                instance = cls()
                instance.deserialize(value)
            except Exception:
                accepts_both = False
                break
        if accepts_both:
            matches.append(cls.__name__)

    return sorted(matches)


# Keep the oracle's stdout restricted to its final JSON result.
with contextlib.redirect_stdout(io.StringIO()):
    answer = compute_answer()

print(json.dumps({"answer": answer}))