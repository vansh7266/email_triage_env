import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import gmail_service


def encode_body(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def test_extract_body_prefers_nested_plain_text():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {"data": encode_body("<p>Hello from <strong>HTML</strong></p>")},
                    },
                    {
                        "mimeType": "text/plain",
                        "body": {"data": encode_body("Plain text body")},
                    },
                ],
            }
        ],
    }

    assert gmail_service._extract_body(payload) == "Plain text body"


def test_extract_body_falls_back_to_html():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": encode_body("<p>Only <strong>HTML</strong> body</p>")},
            }
        ],
    }

    assert gmail_service._extract_body(payload) == "Only HTML body"


def test_parse_sender_decodes_name_and_email():
    sender = "=?UTF-8?B?Sm9obiBEb2U=?= <support@example.com>"
    name, email, display = gmail_service._parse_sender(sender)

    assert name == "John Doe"
    assert email == "support@example.com"
    assert display == "John Doe"


def test_fetch_user_profile_uses_gmail_profile(monkeypatch):
    class FakeProfileRequest:
        def execute(self):
            return {"emailAddress": "triage.owner@example.com"}

    class FakeUsersService:
        def getProfile(self, userId):
            assert userId == "me"
            return FakeProfileRequest()

    class FakeGmailService:
        def users(self):
            return FakeUsersService()

    monkeypatch.setattr(gmail_service, "build_credentials", lambda token_data: object())
    monkeypatch.setattr(
        gmail_service,
        "build",
        lambda *args, **kwargs: FakeGmailService(),
    )

    profile = gmail_service.fetch_user_profile({"token": "sample"})
    assert profile == {
        "email": "triage.owner@example.com",
        "name": "Triage Owner",
    }
