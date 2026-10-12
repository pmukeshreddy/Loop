import io
import json
import sys

sys.dont_write_bytecode = True

from dotenv.parser import parse_stream

contents = json.loads(
    r'"\ufeffexport \'APP NAME\'=\"blue\\nroom\"\n\nBROKEN: value\nTOKEN=#live # note\nEMPTY= # note\nTAIL\n"'.replace("\\'", "'")
)

answer = [
    {
        "key": binding.key,
        "value": binding.value,
        "line": binding.original.line,
        "error": binding.error,
    }
    for binding in parse_stream(io.StringIO(contents))
]

print(json.dumps({"answer": answer}, ensure_ascii=True))