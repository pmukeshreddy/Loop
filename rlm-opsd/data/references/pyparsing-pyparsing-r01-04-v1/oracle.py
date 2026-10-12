import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    repository = Path.cwd().resolve()
    script = repository / "pyparsing/tools/cvt_pyparsing_pep8_names.py"
    originals = {
        "changed.py": "expr.parseString(text)\n",
        "unchanged.py": "expr.parse_string(text)\n",
    }

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repository)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    answer = {}
    with tempfile.TemporaryDirectory(prefix="pyparsing-converter-oracle-") as directory:
        workdir = Path(directory)

        for key, extra_args in (
            ("normal", []),
            ("exit_zero", ["--exit-zero-even-if-changed"]),
        ):
            for name, contents in originals.items():
                (workdir / name).write_bytes(contents.encode("utf-8"))

            command = [
                sys.executable,
                "-B",
                str(script),
                "--update",
                "-vv",
                *extra_args,
                "changed.py",
                "unchanged.py",
                "missing*.py",
            ]

            invocations = []
            for _ in range(2):
                result = subprocess.run(
                    command,
                    cwd=workdir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=12,
                    check=False,
                )
                invocations.append({
                    "stdout": result.stdout.decode("utf-8"),
                    "exit_status": result.returncode,
                    "files": {
                        name: (workdir / name).read_bytes().decode("utf-8")
                        for name in originals
                    },
                })
            answer[key] = invocations

    print(json.dumps({"answer": answer}, ensure_ascii=False))

if __name__ == "__main__":
    main()