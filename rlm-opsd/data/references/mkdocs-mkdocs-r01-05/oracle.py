import sys

sys.dont_write_bytecode = True

import json
from mkdocs.config.base import BaseConfigOption, LegacyConfig, ValidationError


def main():
    trace = []

    class TracedOption(BaseConfigOption):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def pre_validation(self, config, key_name):
            trace.append(f"pre:{self.name}")
            if self.name == "alpha":
                raise ValidationError("alpha pre-validation failed")

        def run_validation(self, value):
            trace.append(f"run:{self.name}")
            if self.name == "beta":
                raise ValidationError("beta run-validation failed")
            return value

        def post_validation(self, config, key_name):
            trace.append(f"post:{self.name}")

    config = LegacyConfig(
        schema=tuple(
            (name, TracedOption(name))
            for name in ("alpha", "beta", "gamma")
        )
    )
    config.load_dict({"alpha": "a", "beta": "b", "gamma": "c"})
    config.validate()

    print(json.dumps({"answer": trace}))


if __name__ == "__main__":
    main()