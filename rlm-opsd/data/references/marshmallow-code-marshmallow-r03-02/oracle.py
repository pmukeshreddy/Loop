import sys
sys.dont_write_bytecode = True

import contextlib
import inspect
import io
import json

from marshmallow import ValidationError, fields


def main():
    # Use the module's declared public exports and deduplicate class aliases.
    classes = {
        cls
        for name in fields.__all__
        if inspect.isclass(cls := getattr(fields, name))
        and issubclass(cls, fields.Field)
        and cls is not fields.Field
        and not inspect.isabstract(cls)
    }

    qualifying = set()
    for cls in sorted(classes, key=lambda c: c.__name__):
        outcomes = []
        for text in ("nan", "inf", "-inf"):
            # A constructor failure means this class is outside the requested
            # no-argument-instantiable scope.
            try:
                field = cls()
            except Exception:
                outcomes.append(False)
                continue

            try:
                serialized = field.serialize("value", {"value": float(text)})
            except Exception:
                outcomes.append(False)
                continue

            try:
                field.deserialize(serialized)
            except ValidationError:
                outcomes.append(True)
            except Exception:
                outcomes.append(False)
            else:
                outcomes.append(False)

        if all(outcomes):
            qualifying.add(cls.__name__)

    return sorted(qualifying)


if __name__ == "__main__":
    # Keep repository output, if any, separate from the oracle's JSON output.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        answer = main()
    print(json.dumps({"answer": answer}, allow_nan=False))