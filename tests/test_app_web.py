import os
import sys
import types

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import app as app_module


def make_session_cookie(**overrides):
    payload = {
        "token": "access-token",
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "user_email": "user@example.com",
        "user_name": "User Example",
    }
    payload.update(overrides)
    return app_module.encrypt_token(payload)


def test_session_cookie_round_trip():
    cookie = make_session_cookie()
    restored = app_module.decrypt_token(cookie)
    assert restored["user_email"] == "user@example.com"
    assert restored["token"] == "access-token"
    assert "client_secret" not in restored


def test_dashboard_redirects_without_session():
    client = TestClient(app_module.app)
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_landing_redirects_with_session():
    client = TestClient(app_module.app)
    client.cookies.set(app_module.SESSION_COOKIE_NAME, make_session_cookie())
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_auth_me_uses_encrypted_session_cookie():
    client = TestClient(app_module.app)
    client.cookies.set(app_module.SESSION_COOKIE_NAME, make_session_cookie())
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json() == {
        "email": "user@example.com",
        "name": "User Example",
    }


def test_auth_callback_stores_minimal_session_payload(monkeypatch):
    client = TestClient(app_module.app)
    client.cookies.set(app_module.OAUTH_STATE_COOKIE, "state-123")
    client.cookies.set(app_module.OAUTH_VERIFIER_COOKIE, "verifier-123")

    monkeypatch.setattr(
        "server.gmail_service.exchange_code",
        lambda code, state, verifier: {
            "token": "access-token",
            "refresh_token": "refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "client_secret": "should-not-leak",
            "client_id": "should-not-leak",
        },
    )
    monkeypatch.setattr(
        "server.gmail_service.fetch_user_profile",
        lambda token_data: {"email": "owner@example.com", "name": "Owner"},
    )

    response = client.get(
        "/auth/callback",
        params={"code": "sample-code", "state": "state-123"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    session_cookie = response.cookies.get(app_module.SESSION_COOKIE_NAME)
    assert session_cookie

    session_data = app_module.decrypt_token(session_cookie)
    assert session_data["user_email"] == "owner@example.com"
    assert session_data["user_name"] == "Owner"
    assert "client_secret" not in session_data
    assert "client_id" not in session_data


def test_auth_login_redirects_to_landing_when_oauth_setup_fails(monkeypatch):
    client = TestClient(app_module.app)

    monkeypatch.setattr(
        "server.gmail_service.get_auth_url",
        lambda: (_ for _ in ()).throw(RuntimeError("Missing Google OAuth configuration")),
    )

    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/?auth_error=")


def test_auth_callback_redirects_to_landing_when_google_returns_error():
    client = TestClient(app_module.app)
    response = client.get(
        "/auth/callback",
        params={"error": "access_denied", "error_description": "User denied access"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "auth_error=Google+sign-in+was+not+completed." in response.headers["location"]


def test_triage_normalizes_model_output(monkeypatch):
    client = TestClient(app_module.app)
    client.cookies.set(app_module.SESSION_COOKIE_NAME, make_session_cookie())

    monkeypatch.setattr(
        "server.gmail_service.fetch_emails",
        lambda *args, **kwargs: (
            [
                {
                    "email_id": "msg-1",
                    "sender": "Acme Billing",
                    "sender_name": "Acme Billing",
                    "sender_email": "billing@acme.test",
                    "subject": "We were charged twice for invoice INV-1042",
                    "body": "Please refund the duplicate charge immediately. The invoice is incorrect and urgent.",
                    "preview": "Please refund the duplicate charge immediately.",
                    "received_at": "2026-05-06T10:00:00+00:00",
                    "urgency_hint": None,
                }
            ],
            None,
        ),
    )

    class FakeCompletions:
        async def create(self, **kwargs):
            content = (
                "```json\n"
                '{"topic":"Customer\'s Billing Emergency","priority":"urgent","department":"support team","escalate":"yes","reasoning":"Duplicate invoice charge with an immediate refund request from a customer."}'
                "\n```"
            )
            message = types.SimpleNamespace(content=content)
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))

    response = client.post("/triage", json={})
    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 1
    result = payload["results"][0]
    assert result["priority"] == "high"
    assert result["department"] == "finance"
    assert result["escalate"] is True
    assert result["topic"] == "Customers Billing Emergency"
    assert result["source"] == "model"
    assert result["preview"] == "Please refund the duplicate charge immediately."
    assert result["score"] >= 0.8


def test_triage_falls_back_to_heuristics_on_model_failure(monkeypatch):
    client = TestClient(app_module.app)
    client.cookies.set(app_module.SESSION_COOKIE_NAME, make_session_cookie())

    monkeypatch.setattr(
        "server.gmail_service.fetch_emails",
        lambda *args, **kwargs: (
            [
                {
                    "email_id": "msg-2",
                    "sender": "Security Desk",
                    "sender_name": "Security Desk",
                    "sender_email": "alerts@example.com",
                    "subject": "Possible data breach detected",
                    "body": "Our team found unauthorized access and needs immediate attention.",
                    "preview": "Unauthorized access needs immediate attention.",
                    "received_at": "2026-05-06T10:00:00+00:00",
                    "urgency_hint": None,
                }
            ],
            None,
        ),
    )

    class BrokenCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("upstream failure")

    class BrokenChat:
        def __init__(self):
            self.completions = BrokenCompletions()

    class BrokenAsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = BrokenChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=BrokenAsyncOpenAI))

    response = client.post("/triage", json={})
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["department"] == "security"
    assert result["priority"] == "high"
    assert result["escalate"] is True
    assert result["topic"] == "Security Alert"
    assert result["source"] == "heuristic"
