import json

from glom import glom
from glom.grouping import Group, Limit, Avg


def main():
    yielded = []

    def target():
        for number in [0, 1, 3, 2, 4, 6, 5, 7, 8]:
            yielded.append(number)
            yield number

    result = glom(target(), Group({(lambda n: n % 3): Limit(2, Avg())}))
    answer = {
        "result": {str(key): value for key, value in result.items()},
        "yielded": yielded,
    }
    print(json.dumps({"answer": answer}))


if __name__ == "__main__":
    main()