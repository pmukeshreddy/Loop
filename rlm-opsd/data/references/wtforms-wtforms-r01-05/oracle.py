import json
from datetime import datetime
from types import SimpleNamespace

from wtforms.csrf.session import SessionCSRF
from wtforms.validators import ValidationError


SESSION = {"csrf": "fixed-session"}
ISSUE_TIME = datetime(2030, 1, 2, 3, 4, 5)


class DefaultMeta:
    csrf_secret = b"secret"
    csrf_context = SESSION
    csrf_field_name = "csrf_token"
    # Deliberately no csrf_time_limit attribute.


class DisabledMeta(DefaultMeta):
    csrf_time_limit = None


def prepare(meta_class):
    form = SimpleNamespace(meta=meta_class())
    implementation = SessionCSRF()
    implementation.now = lambda: ISSUE_TIME
    implementation.setup_form(form)

    field = SimpleNamespace(data=None, gettext=lambda message: message)
    token = implementation.generate_csrf_token(field)
    field.current_token = token
    return implementation, form, field, token


def validate(token, meta_class, validation_time):
    implementation, form, field, _ = prepare(meta_class)
    implementation.now = lambda: validation_time
    field.data = token
    try:
        implementation.validate_csrf_token(form, field)
    except ValidationError as error:
        return str(error)
    return None


def main():
    _, _, _, token_a = prepare(DefaultMeta)
    _, _, _, token_b = prepare(DisabledMeta)

    expires_a, digest_a = token_a.split("##", 1)
    expires_b, _ = token_b.split("##", 1)

    replacement = "0" if digest_a[0] != "0" else "1"
    tampered_a = expires_a + "##" + replacement + digest_a[1:]

    boundary = datetime(2030, 1, 2, 3, 34, 5)
    after_boundary = datetime(2030, 1, 2, 3, 34, 6)
    later = datetime(2031, 1, 2)

    answer = {
        "expires_a": expires_a,
        "expires_b": expires_b,
        "outcomes": {
            "a_at_boundary": validate(token_a, DefaultMeta, boundary),
            "a_after_boundary": validate(token_a, DefaultMeta, after_boundary),
            "b_disabled_later": validate(token_b, DisabledMeta, later),
            "b_with_default_limit": validate(token_b, DefaultMeta, ISSUE_TIME),
            "a_disabled_later": validate(token_a, DisabledMeta, later),
            "tampered_expired_a": validate(
                tampered_a, DefaultMeta, after_boundary
            ),
            "empty_token": validate("", DefaultMeta, ISSUE_TIME),
        },
    }
    print(json.dumps({"answer": answer}))


if __name__ == "__main__":
    main()