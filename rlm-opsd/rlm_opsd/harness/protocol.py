"""Metadata and the SPEC finish protocol; no prompt-template rendering."""
import re
from dataclasses import dataclass, field

from rlm.utils.parsing import find_code_blocks


def context_metadata(context: str | list[str], prefix_chars: int) -> dict:
    if prefix_chars < 0:
        raise ValueError("prefix_chars must be nonnegative")
    if isinstance(context, str):
        return dict(context_type="str", context_total_length=len(context),
                    context_lengths=[], context_prefix=context[:prefix_chars])
    if not isinstance(context, list) or not all(isinstance(c, str) for c in context):
        raise TypeError("context must be str or list[str]")
    lengths = [len(c) for c in context]
    remaining, prefix = prefix_chars, []
    for chunk in context:
        if remaining == 0:
            break
        piece = chunk[:remaining]
        prefix.append(piece)
        remaining -= len(piece)
    return dict(context_type="list", context_total_length=sum(lengths),
                context_lengths=lengths, context_prefix="".join(prefix))


@dataclass
class ParsedTurn:
    code_blocks: list[str] = field(default_factory=list)
    finish_type: str | None = None
    finish_argument: str = ""
    ignored_after_finish: str = ""
    finish_error: str | None = None


def parse_turn(text: str) -> ParsedTurn:
    # Mask every Markdown fence, including non-REPL and unclosed fences. Keep
    # offsets so suffix logging refers to the original, unmodified assistant text.
    outside = list(text)
    blocks: list[tuple[int, int, str]] = []
    fence, opening, start = None, "", 0
    offset = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})([^\n]*)", line)
        if fence is None and match:
            fence, opening, start = match[1], match[2].strip(), offset
        elif fence and match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
            end = offset + len(line)
            if opening == "repl":
                # Canonicalize the fence, then use the pinned reference extractor.
                inner = text[start + len(text[start:].splitlines(keepends=True)[0]):offset]
                extracted = find_code_blocks("```repl\n" + inner.rstrip("\n") + "\n```")
                if extracted:
                    blocks.append((start, end, extracted[0]))
            outside[start:end] = " " * (end - start)
            fence = None
        offset += len(line)
    if fence:
        outside[start:] = " " * (len(text) - start)
    masked = "".join(outside)
    match = re.search(r"(?<!\w)(FINAL_VAR|FINAL)\s*\(", masked)
    result = ParsedTurn()
    boundary = len(text) if match is None else match.start()
    result.code_blocks = [code for start, end, code in blocks if end <= boundary]
    if match is None:
        return result
    depth, quote, escaped = 1, None, False
    for index in range(match.end(), len(masked)):
        char = masked[index]
        if escaped:
            escaped = False
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            # Treat quotation marks as quoting only at an argument/word boundary;
            # contractions such as FINAL(it's done) remain ordinary answer text.
            if index == match.end() or masked[index - 1] in " ([{,":
                quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                result.finish_type = match[1]
                result.finish_argument = text[match.end():index].strip()
                result.ignored_after_finish = text[index + 1:]
                return result
    result.finish_error = "protocol-error: unclosed finish token"
    return result


def truncate_output(prefix: str, total_chars: int, limit: int) -> str:
    value = prefix[:limit]
    if total_chars > limit:
        value += f"\n[truncated: full output length {total_chars} chars]"
    return value
