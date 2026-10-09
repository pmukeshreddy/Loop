"""Project-owned ChatGPT-plan OAuth, using OpenAI's documented PKCE flow."""

import argparse
import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

AUTH_DIR = Path(__file__).resolve().parents[1] / ".phase1-auth"
ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
TOKEN_URL = ISSUER + "/api/accounts/oauth/token"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"


def save_private(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(value, file)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def require_plan_scope(scope: str) -> None:
    if not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(scope.split()):
        raise ValueError(
            "ChatGPT-plan permission was not granted; sign in again and enable it."
        )


def callback_values(
    path: str, expected_state: str, client_id: str | None
) -> tuple[str, str]:
    query = parse_qs(urlparse(path).query)
    if not secrets.compare_digest(query.get("state", [""])[0], expected_state):
        raise ValueError("OAuth state does not match")
    if "error" in query:
        raise ValueError("OAuth authorization denied")
    issued = query.get("client_id", [client_id])[0]
    if (
        not issued
        or issued == "dynamic_agent_client"
        or (client_id and issued != client_id)
    ):
        raise ValueError("OAuth callback has missing or mismatched client_id")
    code = query.get("code", [""])[0]
    if not code:
        raise ValueError("OAuth callback has no authorization code")
    return code, issued


def exchange(data: dict) -> dict:
    response = httpx.post(TOKEN_URL, data=data, timeout=30)
    if response.status_code != 200:
        raise ValueError(
            f"OAuth token exchange failed (HTTP {response.status_code}); sign in again."
        )
    tokens = response.json()
    require_plan_scope(tokens.get("scope", ""))
    if not tokens.get("access_token"):
        raise ValueError("OAuth token exchange did not return an access token")
    return tokens


def credential(mode: str, min_validity: float = 60) -> str:
    if mode == "api-key":
        token = os.environ.get("OPENAI_API_KEY", "")
        if not token:
            raise ValueError("OPENAI_API_KEY is unset; API usage is billed separately.")
        return token
    if mode != "chatgpt":
        raise ValueError(f"Unknown authentication mode: {mode}")
    if os.environ.get("ACCESS_TOKEN"):
        return os.environ["ACCESS_TOKEN"]
    path = AUTH_DIR / "session.json"
    if not path.exists():
        raise ValueError(
            "Run .venv/bin/python -m step1.auth login to authorize this project."
        )
    saved = json.loads(path.read_text())
    require_plan_scope(saved.get("scope", ""))
    if time.time() >= saved["expires_at"] - max(min_validity, 60):
        tokens = exchange(
            {
                "grant_type": "refresh_token",
                "client_id": saved["client_id"],
                "refresh_token": saved["refresh_token"],
                "resource": RESOURCE,
            }
        )
        saved.update(tokens)
        saved["expires_at"] = time.time() + tokens["expires_in"]
        save_private(path, saved)
    return saved["access_token"]


def login() -> None:
    import jwt

    session_path = AUTH_DIR / "session.json"
    saved = json.loads(session_path.read_text()) if session_path.exists() else {}
    registration_path = AUTH_DIR / "registration.json"
    registration = (
        json.loads(registration_path.read_text()) if registration_path.exists() else {}
    )
    client_id = saved.get("client_id") or registration.get("client_id")
    host_path = AUTH_DIR / "host.json"
    if not host_path.exists():
        save_private(host_path, {"id": "urn:uuid:" + str(uuid.uuid4())})
    host_id = json.loads(host_path.read_text())["id"]
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path != "/auth/callback":
                self.send_error(404)
                return
            try:
                result["code"], result["client_id"] = callback_values(
                    self.path, state, client_id
                )
                message = b"Authorization received. Return to your terminal to finish."
                status = 200
            except ValueError as exc:
                result["error"] = exc
                message, status = (
                    b"Authorization was not accepted. Return to your terminal.",
                    400,
                )
            self.send_response(status)
            self.end_headers()
            self.wfile.write(message)

        def log_message(self, *args):
            pass  # Callback URLs contain the authorization code.

    with HTTPServer(("127.0.0.1", 0), Callback) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/auth/callback"
        parameters = {
            "client_id": client_id or "dynamic_agent_client",
            "ext_agent_host_id": host_id,
            "response_type": "code",
            "redirect_uri": redirect,
            "scope": SCOPES,
            "resource": RESOURCE,
            "state": state,
            "nonce": nonce,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        if not client_id:
            parameters["agent_name_hint"] = "Refine DeepSWE"
        print(
            "Open this official sign-in URL and authorize Refine DeepSWE to use your ChatGPT plan:",
            flush=True,
        )
        print(ISSUER + "/api/accounts/authorize?" + urlencode(parameters), flush=True)
        deadline = time.monotonic() + 300
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result:
        raise ValueError("Sign-in timed out; run login again.")
    if "error" in result:
        raise result["error"]
    save_private(registration_path, {"client_id": result["client_id"]})
    tokens = exchange(
        {
            "grant_type": "authorization_code",
            "client_id": result["client_id"],
            "code": result["code"],
            "code_verifier": verifier,
            "redirect_uri": redirect,
            "resource": RESOURCE,
        }
    )
    discovery = httpx.get(ISSUER + "/.well-known/openid-configuration", timeout=30)
    discovery.raise_for_status()
    metadata = discovery.json()
    if metadata["issuer"] != ISSUER:
        raise ValueError("Unexpected OAuth issuer")
    key = jwt.PyJWKClient(metadata["jwks_uri"]).get_signing_key_from_jwt(
        tokens["id_token"]
    )
    claims = jwt.decode(
        tokens["id_token"],
        key.key,
        algorithms=["RS256"],
        audience=result["client_id"],
        issuer=ISSUER,
        options={"require": ["exp", "sub", "nonce"]},
    )
    if claims["nonce"] != nonce or (saved and saved["subject"] != claims["sub"]):
        raise ValueError("OAuth identity or nonce does not match")
    save_private(
        session_path,
        {
            **tokens,
            "client_id": result["client_id"],
            "subject": claims["sub"],
            "ext_agent_host_id": host_id,
            "expires_at": time.time() + tokens["expires_in"],
        },
    )
    print("Signed in for this project. Credentials saved privately; no token printed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("login", "models"))
    parser.add_argument("--auth", choices=("chatgpt", "api-key"), default="chatgpt")
    args = parser.parse_args()
    try:
        if args.command == "login":
            login()
        else:
            response = httpx.get(
                RESOURCE + "/models",
                headers={
                    "Authorization": "Bearer " + credential(args.auth),
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            for model in data.get("models", data.get("data", [])):
                if model.get("visibility", "list") == "list":
                    print(model.get("slug", model.get("id")))
    except (ValueError, httpx.HTTPError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
