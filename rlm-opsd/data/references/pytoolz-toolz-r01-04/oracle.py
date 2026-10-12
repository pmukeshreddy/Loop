import sys

sys.dont_write_bytecode = True

import contextlib
import importlib
import io
import json
import types


def main():
    # Suppress incidental import output so stdout contains only the JSON result.
    with contextlib.redirect_stdout(io.StringIO()):
        import toolz
        import tlz

        builder = importlib.import_module("tlz._build_tlz")
        loader = builder.tlz_loader

        # Ensure none of this fixture's backend or mirrored modules is cached.
        for name in list(sys.modules):
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in ("tlz.audit", "cytoolz.audit", "toolz.audit")
            ):
                del sys.modules[name]

        labels = {
            "fast_curry": object(),
            "slow_curry": object(),
            "fast_pipe": object(),
            "slow_child_curry": object(),
        }

        fast = types.ModuleType("cytoolz.audit", "fast doc")
        fast.__package__ = fast.__name__
        fast.__path__ = []
        fast.__file__ = "fast.py"
        fast.curry = labels["fast_curry"]
        fast.pipe = labels["fast_pipe"]

        slow = types.ModuleType("toolz.audit", "slow doc")
        slow.__package__ = slow.__name__
        slow.__path__ = []
        slow.__file__ = "slow.py"
        slow.curry = labels["slow_curry"]
        slow.pipe = toolz.pipe

        fast_child = types.ModuleType("cytoolz.audit.child")
        fast_child.__package__ = "cytoolz.audit"
        fast.child = fast_child

        slow_child = types.ModuleType("toolz.audit.child")
        slow_child.__package__ = "toolz.audit"
        slow_child.curry = labels["slow_child_curry"]
        slow.child = slow_child

        sys.modules["cytoolz.audit"] = fast
        sys.modules["toolz.audit"] = slow
        sys.modules["toolz.audit.child"] = slow_child

        # The fast child is exported but not importable. Force precisely the
        # stipulated ImportError, independent of any other installed finders.
        class MissingFastChild:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "cytoolz.audit.child":
                    raise ImportError(fullname)
                return None

        blocker = MissingFastChild()
        sys.meta_path.insert(0, blocker)
        try:
            target = types.ModuleType("tlz.audit", "local doc")
            target.__file__ = "local.py"
            sys.modules[target.__name__] = target

            # Recursive mirrored child imports are handled by the installed
            # TlzLoader rather than by manually constructing the result.
            loader.exec_module(target)
        finally:
            sys.meta_path.remove(blocker)

        def object_label(value):
            if value is toolz.pipe:
                return "toolz.pipe"
            for label, obj in labels.items():
                if value is obj:
                    return label
            raise RuntimeError("Unexpected object-valued export")

        answer = {
            "name": target.__name__,
            "package": target.__package__,
            "doc": target.__doc__,
            "file": target.__file__,
            "curry": object_label(target.curry),
            "pipe": object_label(target.pipe),
            "child_name": target.child.__name__,
            "child_curry": object_label(target.child.curry),
        }

    print(json.dumps({"answer": answer}))


if __name__ == "__main__":
    main()