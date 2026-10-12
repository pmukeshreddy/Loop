import json
from jmespath.lexer import Lexer


def main():
    inputs = json.loads(
        r'''["foo =x", "foo =", "foo \"bad\\q\"", "foo 'bad\\"]'''
    )
    records = []

    for expression in inputs:
        lexer = Lexer()
        tokens = []
        try:
            for token in lexer.tokenize(expression):
                tokens.append(token)
        except Exception as exc:
            records.append({
                "tokens": tokens,
                "exception_class": type(exc).__name__,
                "lexer_position": exc.lexer_position,
                "lexer_value": exc.lexer_value,
                "message": exc.message,
                "expression": exc.expression,
                "rendered": str(exc),
            })
        else:
            print(json.dumps({
                "unverifiable": "An input completed without raising an exception."
            }))
            return

    print(json.dumps({"answer": records}, ensure_ascii=False))


if __name__ == "__main__":
    main()