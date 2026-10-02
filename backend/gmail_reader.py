"""Read-only Gmail access (scope gmail.readonly: can't send, delete or change anything)."""

import base64
import html
import re
import threading
from pathlib import Path
from typing import Any, Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
CLIENT_FILE = SECRETS_DIR / "gmail_credentials.json"  # OAuth client, downloaded from Google Cloud
TOKEN_FILE = SECRETS_DIR / "gmail_token.json"  # created once by gmail_auth.py
MAX_EMAIL_CHARS = 6000  # cap on email text sent to the model
LOCK = threading.Lock()  # token refreshes rewrite TOKEN_FILE


def is_configured() -> bool:
    """True once gmail_auth.py has been run and a token exists."""
    return TOKEN_FILE.exists()


def _service():
    """Build a Gmail API client, refreshing (and re-saving) the access token when needed."""
    with LOCK:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds.valid:
            if not creds.refresh_token:
                raise RuntimeError("Gmail login expired. Run gmail_auth.py again on the Mac.")
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _headers(message: Dict[str, Any]) -> Dict[str, str]:
    """Map a message's headers by lowercase name."""
    return {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}


def list_recent(query: str = "", limit: int = 10) -> str:
    """List recent emails (sender, subject, date, preview) matching a Gmail search query."""
    service = _service()
    try:
        found = service.users().messages().list(
            userId="me", q=query or "in:inbox", maxResults=min(max(limit, 1), 20)
        ).execute()
        lines = []
        for ref in found.get("messages", []):
            msg = service.users().messages().get(
                userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            h = _headers(msg)
            unread = " [UNREAD]" if "UNREAD" in msg.get("labelIds", []) else ""
            lines.append(
                f"- id {msg['id']}{unread} | from: {h.get('from', '?')} | subject: {h.get('subject', '(no subject)')}"
                f" | date: {h.get('date', '?')} | preview: {html.unescape(msg.get('snippet', ''))}"
            )
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e.status_code}") from e
    return "\n".join(lines) or "No emails found."


def _decode(data: str) -> str:
    """Decode Gmail's base64url body data."""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _body_text(payload: Dict[str, Any]) -> str:
    """Find the email's text: prefer text/plain, fall back to tag-stripped text/html."""
    parts: List[Dict[str, Any]] = [payload]
    plain, rich = "", ""
    while parts:
        part = parts.pop(0)
        parts.extend(part.get("parts", []))
        data = part.get("body", {}).get("data")
        if not data:
            continue
        if part.get("mimeType") == "text/plain" and not plain:
            plain = _decode(data)
        elif part.get("mimeType") == "text/html" and not rich:
            text = re.sub(r"(?is)<(script|style).*?</\1>", " ", _decode(data))
            rich = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", plain or rich)).strip()


def read(message_id: str) -> str:
    """Return one email's sender, subject, date and text (capped in length)."""
    try:
        msg = _service().users().messages().get(userId="me", id=message_id, format="full").execute()
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e.status_code}. Is the id right?") from e
    h = _headers(msg)
    text = (
        f"From: {h.get('from', '?')}\nSubject: {h.get('subject', '(no subject)')}\nDate: {h.get('date', '?')}\n\n"
        f"{_body_text(msg.get('payload', {})) or '(no text content)'}"
    )
    if len(text) > MAX_EMAIL_CHARS:
        text = text[:MAX_EMAIL_CHARS] + "\n...(truncated)"
    return text
