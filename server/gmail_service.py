import base64
import os
import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr
from html import unescape
from typing import Any

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def _require_oauth_env() -> None:
    missing = [
        name
        for name, value in (
            ("GOOGLE_CLIENT_ID", CLIENT_ID),
            ("GOOGLE_CLIENT_SECRET", CLIENT_SECRET),
            ("GOOGLE_REDIRECT_URI", REDIRECT_URI),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing Google OAuth configuration: " + ", ".join(sorted(missing))
        )


def build_credentials(token_data: dict) -> Credentials:
    _require_oauth_env()
    return Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=token_data.get("scopes", SCOPES),
    )


def get_auth_url() -> tuple[str, str, str | None]:
    _require_oauth_env()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state, getattr(flow, "code_verifier", None)


def exchange_code(code: str, state: str, code_verifier: str) -> dict[str, Any]:
    _require_oauth_env()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI,
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "scopes": list(creds.scopes) if creds.scopes else list(SCOPES),
    }


def fetch_user_profile(token_data: dict) -> dict[str, str]:
    creds = build_credentials(token_data)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    info = service.users().getProfile(userId="me").execute()
    email = info.get("emailAddress", "")
    return {
        "email": email,
        "name": _display_name_from_email(email),
    }


def fetch_emails(
    token_data: dict,
    max_results: int = 10,
    page_token: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    creds = build_credentials(token_data)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    request_kwargs = {
        "userId": "me",
        "maxResults": max_results,
        "q": "is:unread",
        "includeSpamTrash": False,
    }
    if page_token:
        request_kwargs["pageToken"] = page_token

    results = service.users().messages().list(**request_kwargs).execute()
    messages = results.get("messages", [])
    next_page_token = results.get("nextPageToken")

    emails: list[dict[str, Any]] = []
    for message in messages:
        try:
            parsed = _fetch_message(service, message["id"])
            if parsed:
                emails.append(parsed)
        except Exception:
            continue

    return emails, next_page_token


def _fetch_message(service: Any, message_id: str) -> dict[str, Any]:
    msg_data = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()
    payload = msg_data.get("payload", {})
    headers_list = payload.get("headers", [])
    headers = {
        header["name"]: _decode_mime_header(header["value"])
        for header in headers_list
        if header.get("name")
    }

    sender_name, sender_email, sender_display = _parse_sender(headers.get("From", ""))
    subject = headers.get("Subject", "No Subject") or "No Subject"
    body = _extract_body(payload)
    snippet = _clean_text(msg_data.get("snippet", ""))
    body_text = _clean_text(body) or snippet or "No preview available."
    preview = _truncate(body_text, 220)

    return {
        "email_id": message_id,
        "sender": sender_display,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "subject": subject,
        "body": _truncate(body_text, 1800),
        "preview": preview,
        "received_at": _parse_internal_date(msg_data.get("internalDate")),
        "urgency_hint": None,
    }


def _parse_sender(value: str) -> tuple[str, str, str]:
    decoded = _decode_mime_header(value)
    name, email_address = parseaddr(decoded)
    clean_name = _clean_text(name)
    clean_email = _clean_text(email_address)

    if clean_name and clean_email and clean_name != clean_email:
        return clean_name, clean_email, clean_name
    if clean_email:
        return clean_email, clean_email, clean_email
    fallback = _clean_text(decoded) or "Unknown Sender"
    return fallback, "", fallback


def _decode_mime_header(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _decode_body_data(data: str) -> str:
    if not data:
        return ""
    padded = data + ("=" * (-len(data) % 4))
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return decoded.decode("utf-8", errors="ignore")


def _strip_html(value: str) -> str:
    no_tags = HTML_TAG_RE.sub(" ", value)
    return _clean_text(no_tags)


def _clean_text(value: str) -> str:
    if not value:
        return ""
    normalized = unescape(value).replace("\u200b", " ").replace("\xa0", " ")
    normalized = normalized.replace("\r", "\n")
    return WHITESPACE_RE.sub(" ", normalized).strip()


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    clipped = value[: limit - 1].rstrip()
    return f"{clipped}…"


def _display_name_from_email(value: str) -> str:
    if not value or "@" not in value:
        return ""
    local_part = value.split("@", 1)[0]
    cleaned = re.sub(r"[._-]+", " ", local_part).strip()
    if not cleaned:
        return local_part
    return " ".join(part.capitalize() for part in cleaned.split())


def _parse_internal_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _extract_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return _clean_text(_decode_body_data(payload.get("body", {}).get("data", "")))

    if mime_type == "text/html":
        html = _decode_body_data(payload.get("body", {}).get("data", ""))
        return _strip_html(html)

    if mime_type.startswith("multipart/"):
        parts = payload.get("parts", [])

        for part in parts:
            if part.get("mimeType") == "text/plain":
                text = _extract_body(part)
                if text:
                    return text

        for part in parts:
            if part.get("mimeType", "").startswith("multipart/"):
                nested = _extract_body(part)
                if nested:
                    return nested

        for part in parts:
            if part.get("mimeType") == "text/html":
                html_text = _extract_body(part)
                if html_text:
                    return html_text

    return _clean_text(_decode_body_data(payload.get("body", {}).get("data", "")))
