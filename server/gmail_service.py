import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_auth_url() -> tuple:
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
    return auth_url, state, getattr(flow, 'code_verifier', None)

def exchange_code(code: str, state: str, code_verifier: str) -> dict:
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
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
    }

def fetch_emails(token_data: dict, max_results: int = 10, page_token: str = None) -> tuple[list, str]:
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes", SCOPES),
    )
    service = build("gmail", "v1", credentials=creds)
    request_kwargs = {"userId": "me", "maxResults": max_results, "q": "is:unread"}
    if page_token:
        request_kwargs["pageToken"] = page_token
        
    results = service.users().messages().list(**request_kwargs).execute()
    messages = results.get("messages", [])
    next_page_token = results.get("nextPageToken")
    emails = []
    for msg in messages:
        try:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()
            payload = msg_data.get("payload", {})
            headers_list = payload.get("headers", [])
            headers = {h["name"]: h["value"] for h in headers_list}
            body = _extract_body(payload)
            emails.append({
                "email_id": msg["id"],
                "sender": headers.get("From", ""),
                "subject": headers.get("Subject", "No Subject"),
                "body": body[:1000],
                "urgency_hint": None,
            })
        except Exception:
            # Skip emails that fail to parse rather than crashing the whole batch
            continue
    return emails, next_page_token


def _extract_body(payload: dict) -> str:
    """
    Recursively extract plain text body from Gmail MIME payload.
    Handles nested multipart structures (multipart/mixed → multipart/alternative → text/plain).
    """
    mime_type = payload.get("mimeType", "")

    # Direct text/plain body
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return ""

    # Multipart — recurse into parts
    if mime_type.startswith("multipart/"):
        parts = payload.get("parts", [])
        # First pass: look for text/plain
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        # Second pass: recurse into nested multipart
        for part in parts:
            if part.get("mimeType", "").startswith("multipart/"):
                result = _extract_body(part)
                if result:
                    return result
        # Third pass: fallback to text/html if no plain text found
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    # Strip HTML tags for a rough plain text extraction
                    import re
                    return re.sub(r"<[^>]+>", " ", html).strip()

    # Fallback: try body.data directly (some simple messages)
    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return ""