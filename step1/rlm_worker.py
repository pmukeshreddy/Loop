"""Process boundary for the official RLM so a stuck REPL can be terminated."""

import json
import os
import sys
from pathlib import Path

from step1.run_eval import complete_rlm


def main() -> None:
    request = json.load(sys.stdin)
    patch, evidence = complete_rlm(
        request["model"],
        os.environ["DEEPSWE_OPENAI_TOKEN"],
        Path(request["output"]),
        request["timeout"],
    )
    print(json.dumps({"patch": patch, "evidence": evidence}))


if __name__ == "__main__":
    main()
