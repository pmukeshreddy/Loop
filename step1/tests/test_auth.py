"""Authentication stays explicit and fails closed on incomplete consent."""

import io
import os
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse

import pytest


def test_callback_rejects_wrong_state_and_missing_registration():
    from step1 import auth

    with pytest.raises(ValueError, match="state"):
        auth.callback_values(
            "/auth/callback?state=wrong&code=c&client_id=oaiapp_x", "expected", None
        )
    with pytest.raises(ValueError, match="client_id"):
        auth.callback_values("/auth/callback?state=s&code=c", "s", None)
    with pytest.raises(ValueError, match="denied"):
        auth.callback_values("/auth/callback?state=s&error=access_denied", "s", None)
    with pytest.raises(ValueError, match="client_id"):
        auth.callback_values(
            "/auth/callback?state=s&code=c&client_id=oaiapp_wrong", "s", "oaiapp_saved"
        )
    assert auth.callback_values(
        "/auth/callback?state=s&code=c", "s", "oaiapp_saved"
    ) == ("c", "oaiapp_saved")


def test_auth_does_not_fall_back_to_paid_key(monkeypatch, tmp_path):
    from step1 import auth

    monkeypatch.setattr(auth, "AUTH_DIR", tmp_path)
    monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "paid-key")
    with pytest.raises(ValueError, match="login"):
        auth.credential("chatgpt")
    assert auth.credential("api-key") == "paid-key"


def test_saved_token_is_private_and_requires_plan_scope(tmp_path):
    from step1 import auth

    auth.save_private(tmp_path / "session.json", {"access_token": "secret"})
    assert os.stat(tmp_path / "session.json").st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="permission"):
        auth.require_plan_scope("openid profile email")
    auth.require_plan_scope("openid resource.invoke chatgpt.tokens.use.direct")


def test_refresh_covers_the_entire_attempt_budget(monkeypatch, tmp_path):
    from step1 import auth

    monkeypatch.setattr(auth, "AUTH_DIR", tmp_path)
    monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    auth.save_private(
        tmp_path / "session.json",
        {
            "access_token": "almost-expired",
            "refresh_token": "refresh",
            "client_id": "app",
            "scope": auth.SCOPES,
            "expires_at": time.time() + 300,
        },
    )
    monkeypatch.setattr(
        auth,
        "exchange",
        lambda data: {
            "access_token": "renewed",
            "expires_in": 3600,
            "scope": auth.SCOPES,
        },
    )
    assert auth.credential("chatgpt", min_validity=660) == "renewed"


def test_failed_exchange_reuses_issued_registration(monkeypatch, tmp_path):
    from step1 import auth

    messages = []
    client_ids = []
    monkeypatch.setattr(auth, "AUTH_DIR", tmp_path)
    monkeypatch.setattr("builtins.print", lambda text, **kwargs: messages.append(text))

    class Server:
        server_port = 1455

        def __init__(self, address, handler):
            self.handler = handler

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def handle_request(self):
            query = parse_qs(urlparse(messages[-1]).query)
            client_ids.append(query["client_id"][0])
            request = SimpleNamespace(
                path="/auth/callback?"
                + urlencode(
                    {
                        "state": query["state"][0],
                        "code": "expired",
                        "client_id": "oaiapp_issued",
                    }
                ),
                send_response=lambda status: None,
                end_headers=lambda: None,
                wfile=io.BytesIO(),
            )
            self.handler.do_GET(request)

    def reject(data):
        raise ValueError("invalid_grant")

    monkeypatch.setattr(auth, "HTTPServer", Server)
    monkeypatch.setattr(auth, "exchange", reject)
    for _ in range(2):
        with pytest.raises(ValueError, match="invalid_grant"):
            auth.login()
    assert client_ids == ["dynamic_agent_client", "oaiapp_issued"]
