import sys

sys.dont_write_bytecode = True

import inspect
import json
import pickle
from pathlib import Path

# Ensure imports exercise the checkout rather than another installed copy.
root = Path.cwd().resolve()
sys.path.insert(0, str(root / "src"))

import attr


def main():
    if not Path(attr.__file__).resolve().is_relative_to(root):
        return {"unverifiable": "attr was not imported from the repository checkout."}

    @attr.s
    class Omitted:
        _private = attr.ib()

    @attr.s
    class Private:
        _private = attr.ib(alias="private")

    @attr.s
    class Custom:
        _private = attr.ib(alias="custom")

    declarations = [
        ("omitted", attr.fields(Omitted)[0]),
        ("private", attr.fields(Private)[0]),
        ("custom", attr.fields(Custom)[0]),
    ]

    if attr.Attribute.__slots__[-1] != "alias_is_default":
        return {
            "unverifiable": "The snapshot does not have alias_is_default as its final Attribute slot."
        }

    legacy_states = [
        (label, attribute.__getstate__()[:-1])
        for label, attribute in declarations
    ]

    groups = []
    consumed = set()
    for i, (label, state) in enumerate(legacy_states):
        if i in consumed:
            continue
        group = [label]
        consumed.add(i)
        for j in range(i + 1, len(legacy_states)):
            if j not in consumed and legacy_states[j][1] == state:
                group.append(legacy_states[j][0])
                consumed.add(j)
        if len(group) >= 2:
            groups.append(group)

    rows = []
    for restoration_format in ("current", "legacy"):
        for label, decorated_attribute in declarations:
            if restoration_format == "current":
                restored = pickle.loads(
                    pickle.dumps(
                        decorated_attribute, protocol=pickle.HIGHEST_PROTOCOL
                    )
                )
            else:
                restored = object.__new__(attr.Attribute)
                restored.__setstate__(decorated_attribute.__getstate__()[:-1])

            before = restored.__getstate__()
            restored_alias_is_default = restored.alias_is_default
            assert isinstance(restored_alias_is_default, bool)

            evolved = restored.evolve(name="_renamed")
            renamed_alias = evolved.alias
            input_mutated = restored.__getstate__() != before

            def transformer(cls, attributes):
                assert not attributes
                return [evolved]

            class Empty:
                pass

            resulting_class = attr.s(
                slots=False, field_transformer=transformer
            )(Empty)

            input_mutated = (
                input_mutated or restored.__getstate__() != before
            )

            parameters = list(
                inspect.signature(resulting_class.__init__).parameters.values()
            )
            field_parameters = parameters[1:]
            assert len(field_parameters) == 1
            parameter = field_parameters[0]
            assert parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
            constructor_keyword = parameter.name

            # Exercise the generated initializer, not just its signature.
            instance = resulting_class(**{constructor_keyword: 123})
            assert getattr(instance, "_renamed") == 123

            rows.append(
                {
                    "format": restoration_format,
                    "declaration": label,
                    "restored_alias_is_default": restored_alias_is_default,
                    "renamed_alias": renamed_alias,
                    "input_mutated": input_mutated,
                    "constructor_keyword": constructor_keyword,
                }
            )

    return {
        "answer": {
            "rows": rows,
            "legacy_indistinguishable_declarations": groups,
        }
    }


if __name__ == "__main__":
    print(json.dumps(main()))