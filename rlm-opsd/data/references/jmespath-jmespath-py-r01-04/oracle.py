import json

from jmespath.lexer import Lexer


def main():
    expression = """foo."bar" | 'x'"""
    tokens = list(Lexer().tokenize(expression))
    print(json.dumps({"answer": tokens}, ensure_ascii=False))


if __name__ == "__main__":
    main()