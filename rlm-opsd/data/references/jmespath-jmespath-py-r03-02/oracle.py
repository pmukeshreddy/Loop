import sys
sys.dont_write_bytecode = True

import itertools
import json
import os

sys.path.insert(0, os.getcwd())

import jmespath
from jmespath.functions import Functions


def main():
    functions = Functions()

    # Ordinary JSON values covering empty/nonempty collections, every JSON
    # type, conversion boundaries, and homogeneous/heterogeneous arrays.
    scalars = [
        None, False, True,
        -2, -1, 0, 1, 2, -1.5, 0.0, 1.5,
        "", "a", "z", "0", "-2", "1.5", "not-a-number",
    ]
    objects = [
        {},
        {"key": None},
        {"key": 0},
        {"key": "a"},
        {"nested": {"key": 1}},
    ]
    arrays = [
        [],
        [None],
        [False, True],
        [-2, 0, 2],
        [1.5, -1.5],
        ["a", "z"],
        ["", "a"],
        [None, 0],
        [0, "a"],
        [[], {}],
        [{"key": 2}, {"key": 1}],
        [{"key": "z"}, {"key": "a"}],
        [{"key": None}, {}],
    ]
    arrays.extend([[value] for value in scalars + objects])

    # Round-trip through JSON so no Python-specific data classes enter the
    # corpus. Expression references are created by the actual interpreter.
    json_values = json.loads(json.dumps(scalars + objects + arrays))
    expression_sources = [
        "&@",
        "&key",
        "&missing",
        "&nested.key",
        "&`null`",
        "&`0`",
        '&`"a"`',
        "&type(@)",
        "&to_number(@)",
        "&length(@)",
    ]
    references = [
        jmespath.search(source, None)
        for source in expression_sources
    ]
    values = json_values + references

    def candidates_for(spec, name):
        allowed = spec["types"]
        if not allowed:
            return values
        candidates = []
        for value in values:
            try:
                functions._type_check_single(value, allowed, name)
            except Exception:
                continue
            candidates.append(value)
        return candidates

    nullable = []
    for name, registration in sorted(functions.FUNCTION_TABLE.items()):
        signature = registration["signature"]
        pools = [candidates_for(spec, name) for spec in signature]

        # Exercise the minimum arity and an additional variadic argument.
        # The repository validator determines validity, including its actual
        # handling of variadic arguments.
        argument_pools = [pools]
        if signature and signature[-1].get("variadic"):
            argument_pools.append(pools + [values])

        witnessed_null = False
        witnessed_success = False
        for current_pools in argument_pools:
            for args in itertools.product(*current_pools):
                try:
                    functions._validate_arguments(args, signature, name)
                    result = functions.call_function(name, list(args))
                except Exception:
                    continue
                witnessed_success = True
                if result is None:
                    nullable.append(name)
                    witnessed_null = True
                    break
            if witnessed_null:
                break

        if not witnessed_success:
            print(json.dumps({
                "unverifiable":
                    "No successful signature-valid execution constructed "
                    "for registered function " + name
            }))
            return

    print(json.dumps({"answer": sorted(nullable)}))


if __name__ == "__main__":
    main()