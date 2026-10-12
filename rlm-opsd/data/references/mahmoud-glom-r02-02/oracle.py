import sys
sys.dont_write_bytecode = True

import json
import glom as package
from glom import (
    glom, Coalesce, Spec, T, Regex, Match, And, Or, Switch, Val, Check,
    GlomError,
)


def fallback_callable(argument):
    return argument["fallback"]


def validate_false(argument):
    return False


def validate_raise(argument):
    raise ValueError("rejected")


def public_exception_name(exc):
    # glom can generate wrapper exception types. Select the nearest
    # exception class in the MRO exposed by the public package API.
    public_classes = {
        value
        for value in vars(package).values()
        if isinstance(value, type) and issubclass(value, GlomError)
    }
    for cls in type(exc).__mro__:
        if cls in public_classes:
            return cls.__name__
    raise RuntimeError(
        f"Failure has no public glom exception class: {type(exc).__name__}"
    )


def main():
    factories = {
        "coalesce": lambda default: Coalesce(Regex("ok"), default=default),
        "match": lambda default: Match(Regex("ok"), default=default),
        "and": lambda default: And(Regex("ok"), default=default),
        "or": lambda default: Or(Regex("ok"), default=default),
        "switch": lambda default: Switch(
            [(Regex("ok"), Val("unused"))], default=default
        ),
        "check_type": lambda default: Check(
            "candidate", type=int, default=default
        ),
        "check_false": lambda default: Check(
            "candidate", validate=validate_false, default=default
        ),
        "check_raise": lambda default: Check(
            "candidate", validate=validate_raise, default=default
        ),
    }

    answer = {}
    for row, factory in factories.items():
        results = []
        defaults = ["fallback", Spec(T["fallback"]), fallback_callable]
        for default in defaults:
            target = {"candidate": "bad", "fallback": "recovered"}
            spec = factory(default)
            try:
                result = glom(target, spec, glom_debug=False)
            except Exception as exc:
                results.append(public_exception_name(exc))
            else:
                if result is default:
                    results.append("default")
                elif isinstance(result, str) and result == "recovered":
                    results.append("recovered")
                else:
                    return {
                        "unverifiable":
                        f"Unexpected successful result in row {row}: "
                        f"{type(result).__name__}"
                    }
        answer[row] = results
    return {"answer": answer}


try:
    output = main()
except Exception as exc:
    output = {
        "unverifiable": f"Oracle execution failed: {type(exc).__name__}: {exc}"
    }

print(json.dumps(output, sort_keys=True))