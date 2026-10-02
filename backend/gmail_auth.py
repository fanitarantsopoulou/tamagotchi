"""One-time Gmail login. Run on the Mac (not in Docker), it opens the browser:

    .venv/bin/python backend/gmail_auth.py

Saves secrets/gmail_token.json, which the container uses from then on.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_reader import CLIENT_FILE, SCOPES, TOKEN_FILE


def main() -> None:
    """Run Google's browser login for read-only Gmail access and store the token."""
    if not CLIENT_FILE.exists():
        raise SystemExit(f"Missing {CLIENT_FILE}. Download the OAuth client JSON from Google Cloud and save it there.")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Done! Saved {TOKEN_FILE}. Restart the container: docker compose up -d --force-recreate")


if __name__ == "__main__":
    main()
