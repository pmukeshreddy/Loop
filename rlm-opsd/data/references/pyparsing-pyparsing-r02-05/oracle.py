import ast
import contextlib
import importlib
import io
import json
import sys
from pathlib import Path

# Avoid creating bytecode files in the checkout.
sys.dont_write_bytecode = True


def run():
    source_path = Path.cwd() / "dest" / "inv_regex.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    main_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    tests_assignment = next(
        node
        for node in main_node.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "tests"
            for target in node.targets
        )
    )

    # Extract only the static demonstration input, without executing main(),
    # which prints examples and expands patterns more than once.
    value = tests_assignment.value
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "splitlines"
        and not value.args
        and not value.keywords
        and isinstance(value.func.value, ast.Constant)
        and isinstance(value.func.value.value, str)
    ):
        return {"unverifiable": "The demonstration corpus is not a literal string split into lines."}

    patterns = [
        line.strip()
        for line in ast.literal_eval(value.func.value).splitlines()
        if line.strip()
    ]

    # This standalone program imports the inverter once, in its fresh state.
    inv_regex = importlib.import_module("dest.inv_regex")
    from pyparsing import ParseFatalException

    answer = {}
    for pattern in patterns:
        try:
            answer[pattern] = {"count": inv_regex.count(inv_regex.invert(pattern))}
        except ParseFatalException as exc:
            answer[pattern] = {"error": exc.msg}

    return {"answer": answer}


if __name__ == "__main__":
    # Keep the final JSON as the only stdout output.
    with contextlib.redirect_stdout(io.StringIO()):
        result = run()
    print(json.dumps(result, ensure_ascii=True))