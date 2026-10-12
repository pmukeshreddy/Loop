import sys

sys.dont_write_bytecode = True

import json
from html.parser import HTMLParser

from wtforms import Form
from wtforms.fields.datetime import DateTimeLocalField, MonthField, WeekField


class FormData(dict):
    def getlist(self, key):
        return list(self.get(key, []))


class DateControls(Form):
    local = DateTimeLocalField()
    month = MonthField()
    week = WeekField()


class InputValueParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "input":
            attributes = dict(attrs)
            self.values.append(attributes.get("value", ""))


def rendered_value(field):
    parser = InputValueParser()
    parser.feed(str(field()))
    parser.close()
    if len(parser.values) != 1:
        raise RuntimeError("Expected exactly one rendered input.")
    return parser.values[0]


def main():
    form = DateControls(
        formdata=FormData(
            local=["2025-04-06T07:08"],
            month=["2025-04"],
            week=["2025-W01"],
        )
    )

    if not form.validate():
        print(json.dumps({"unverifiable": f"Submissions failed validation: {form.errors}"}))
        return

    answer = {}
    for name in ("local", "month", "week"):
        field = getattr(form, name)
        entry = {
            "type": type(field.data).__name__,
            "data": field.data.isoformat(),
            "submitted_value": rendered_value(field),
        }
        field.raw_data = None
        entry["no_raw_value"] = rendered_value(field)
        answer[name] = entry

    print(json.dumps({"answer": answer}))


if __name__ == "__main__":
    main()