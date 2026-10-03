"""One Google login for all Google integrations (Gmail + Calendar), read-only.

First time (and again if the login expires), run on the Mac, not in Docker; it opens the browser:

    .venv/bin/python backend/google_auth.py

It saves secrets/google_token.json, which the container then uses and refreshes by itself.
While the Google Cloud app is in "Testing" status, Google expires the login after 7 days.
"""

import threading
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
CLIENT_FILE = SECRETS_DIR / "google_credentials.json"  # OAuth client, downloaded from Google Cloud
TOKEN_FILE = SECRETS_DIR / "google_token.json"  # created by running this file

# Read-only access: nothing can be sent, deleted or changed.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
LOGIN_HINT = "Run: .venv/bin/python backend/google_auth.py"
_lock = threading.Lock()  # token refreshes rewrite TOKEN_FILE


class GoogleAuthError(Exception):
    """Not logged in, or the login expired: the user has to run this file again."""


def is_configured() -> bool:
    """True once the login has been done and a token exists."""
    return TOKEN_FILE.exists()


def credentials() -> Credentials:
    """Valid credentials, refreshing (and re-saving) the access token when needed."""
    if not TOKEN_FILE.exists():
        raise GoogleAuthError(f"Not connected to Google. {LOGIN_HINT}")
    with _lock:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.valid:
            return creds
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise GoogleAuthError(f"Google login expired. {LOGIN_HINT}") from e
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def login() -> None:
    """Browser login for read-only Gmail + Calendar access; stores the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow  # only needed for the one-time login

    if not CLIENT_FILE.exists():
        raise SystemExit(f"Missing {CLIENT_FILE}. Download the OAuth client JSON from Google Cloud and save it there.")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_FILE.write_text(creds.to_json())
    TOKEN_FILE.chmod(0o600)
    print(f"Done! Saved {TOKEN_FILE}. The app picks it up automatically.")


if __name__ == "__main__":
    login()
