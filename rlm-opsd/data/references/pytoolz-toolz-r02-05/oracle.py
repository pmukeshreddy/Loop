import sys
sys.dont_write_bytecode = True

import contextlib
import importlib
import io
import json
import types
from unittest.mock import patch


def main():
    # Initialize the real package before installing the isolated fixtures.
    with contextlib.redirect_stdout(io.StringIO()):
        implementation = importlib.import_module("tlz._build_tlz")

    fixtures = {
        "both": (True, True),
        "cytoolz_only": (True, False),
        "toolz_only": (False, True),
        "neither": (False, False),
    }
    answer = {}

    for fixture_name, (cytoolz_available, toolz_available) in fixtures.items():
        attempts = []

        def fixture_import(module_name, package=None):
            attempts.append(module_name)
            if module_name == "cytoolz.audit":
                if cytoolz_available:
                    return types.ModuleType(module_name)
                raise ModuleNotFoundError(
                    "missing dependency",
                    name="cytoolz.audit.dependency",
                )
            if module_name == "toolz.audit":
                if toolz_available:
                    return types.ModuleType(module_name)
                raise ImportError("toolz initialization failed")
            raise RuntimeError(f"Unexpected fixture import: {module_name}")

        loader = implementation.TlzLoader()
        with patch.object(implementation, "import_module", fixture_import):
            try:
                result = loader._load_toolz("tlz.audit")
            except Exception as exc:
                backends = []
                error_args = list(exc.args)
            else:
                backends = sorted(result.keys())
                error_args = None

        answer[fixture_name] = {
            "attempts": attempts,
            "backends": backends,
            "error_args": error_args,
        }

    print(json.dumps({"answer": answer}))


if __name__ == "__main__":
    main()