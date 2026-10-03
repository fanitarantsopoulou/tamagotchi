"""Spotify: what's playing now, playlist search and playback control (playback needs Premium).

Login uses OAuth with PKCE (no client secret). First time, run on the Mac, not in Docker:

    .venv/bin/python backend/spotify_client.py

It opens the browser and saves secrets/spotify_token.json; the app refreshes it by itself.
Needs SPOTIFY_CLIENT_ID in .env and the redirect URI http://127.0.0.1:8765/callback registered
in the Spotify Developer Dashboard.
"""

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

TOKEN_FILE = Path(__file__).resolve().parent.parent / "secrets" / "spotify_token.json"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
SCOPES = "user-read-currently-playing user-read-playback-state user-modify-playback-state"
TIMEOUT_SECONDS = 8
NOW_PLAYING_TTL = 3  # seconds; several open pages polling don't multiply API calls
LOGIN_HINT = "Run: .venv/bin/python backend/spotify_client.py"

_token_lock = threading.Lock()
_now_cache: Dict[str, Any] = {"at": 0.0, "value": None}


class SpotifyError(Exception):
    """A problem with a short message that's safe to show (not connected, no device, ...)."""


def client_id() -> str:
    return os.environ.get("SPOTIFY_CLIENT_ID", "").strip()


def is_configured() -> bool:
    """True once there's a client id and the login has been done."""
    return bool(client_id()) and TOKEN_FILE.exists()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _request(method: str, url: str, *, headers=None, data: Optional[bytes] = None):
    """Send a request; returns (status, parsed JSON or None). Network errors -> SpotifyError."""
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
            body = res.read()
            return res.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body) if body else None
        except ValueError:
            return e.code, None
    except (OSError, ValueError) as e:
        raise SpotifyError(f"Spotify unreachable ({e.__class__.__name__})") from e


def _token_request(fields: Dict[str, str]) -> Dict[str, Any]:
    """POST to the accounts token endpoint (code exchange or refresh)."""
    status, data = _request(
        "POST",
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=urllib.parse.urlencode(fields).encode(),
    )
    if status != 200 or not data:
        raise SpotifyError(f"Spotify login failed or expired. {LOGIN_HINT}")
    return data


def _save_token(data: Dict[str, Any], old_refresh: Optional[str] = None) -> Dict[str, Any]:
    token = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token") or old_refresh,  # Spotify may not send a new one
        "expires_at": time.time() + data.get("expires_in", 3600) - 60,
    }
    TOKEN_FILE.write_text(json.dumps(token))
    TOKEN_FILE.chmod(0o600)
    return token


def _access_token() -> str:
    """A valid access token, refreshed when it's about to expire."""
    if not client_id():
        raise SpotifyError("SPOTIFY_CLIENT_ID is missing from .env.")
    if not TOKEN_FILE.exists():
        raise SpotifyError(f"Spotify isn't connected. {LOGIN_HINT}")
    with _token_lock:
        token = json.loads(TOKEN_FILE.read_text())
        if time.time() >= token["expires_at"]:
            data = _token_request(
                {"grant_type": "refresh_token", "refresh_token": token["refresh_token"], "client_id": client_id()}
            )
            token = _save_token(data, token["refresh_token"])
    return token["access_token"]


def _api(method: str, path: str, body: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None):
    """Call the Web API; returns (status, json)."""
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    headers = {"Authorization": f"Bearer {_access_token()}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    elif method in ("PUT", "POST"):
        data = b""
    return _request(method, url, headers=headers, data=data)


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
def now_playing(fresh: bool = False) -> Optional[Dict[str, Any]]:
    """The current track (title, artists, album art, progress), or None if nothing is playing."""
    if not fresh and time.time() - _now_cache["at"] < NOW_PLAYING_TTL:
        return _now_cache["value"]
    status, data = _api("GET", "/me/player/currently-playing", params={"additional_types": "track,episode"})
    if status == 401:
        raise SpotifyError(f"Spotify login expired. {LOGIN_HINT}")
    value = None
    if status == 200 and data and data.get("item"):
        item = data["item"]
        images = (item.get("album") or item.get("show") or {}).get("images") or []
        value = {
            "is_playing": data.get("is_playing", False),
            "title": item.get("name", ""),
            "artists": ", ".join(a["name"] for a in item.get("artists", [])) or (item.get("show") or {}).get("name", ""),
            "album": (item.get("album") or {}).get("name", ""),
            "image": images[-2]["url"] if len(images) > 1 else (images[0]["url"] if images else None),  # ~300px
            "progress_ms": data.get("progress_ms") or 0,
            "duration_ms": item.get("duration_ms") or 0,
            "url": (item.get("external_urls") or {}).get("spotify"),
        }
    _now_cache.update(at=time.time(), value=value)
    return value


def find_playlists(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search public playlists; returns name, owner, link and uri for each."""
    status, data = _api("GET", "/search", params={"q": query, "type": "playlist", "limit": max(1, min(limit, 10))})
    if status != 200 or not data:
        raise SpotifyError("Playlist search failed.")
    items = [p for p in (data.get("playlists") or {}).get("items", []) if p]  # Spotify may return nulls
    return [
        {
            "name": p.get("name", ""),
            "owner": (p.get("owner") or {}).get("display_name", ""),
            "uri": p.get("uri"),
            "url": (p.get("external_urls") or {}).get("spotify"),
        }
        for p in items
    ]


def _first_device_id() -> Optional[str]:
    status, data = _api("GET", "/me/player/devices")
    devices = (data or {}).get("devices", []) if status == 200 else []
    active = [d for d in devices if d.get("is_active")]
    chosen = (active or devices or [None])[0]
    return chosen["id"] if chosen else None


def play(context_uri: Optional[str] = None) -> None:
    """Start/resume playback (optionally a playlist uri) on the active or first available device."""
    if context_uri and not context_uri.startswith("spotify:playlist:"):
        raise SpotifyError("Only Spotify playlist URIs can be played.")
    body = {"context_uri": context_uri} if context_uri else None
    status, data = _api("PUT", "/me/player/play", body=body)
    if status == 404:  # no active device: wake up the first available one
        device = _first_device_id()
        if not device:
            raise SpotifyError("No Spotify device found. Open Spotify on your phone or computer first.")
        status, data = _api("PUT", "/me/player/play", body=body, params={"device_id": device})
    _check_playback(status, data)


def control(action: str) -> None:
    """pause / next / previous / play."""
    if action == "play":
        return play()
    routes = {"pause": ("PUT", "/me/player/pause"), "next": ("POST", "/me/player/next"), "previous": ("POST", "/me/player/previous")}
    if action not in routes:
        raise SpotifyError(f"Unknown action: {action}")
    status, data = _api(*routes[action])
    _check_playback(status, data)


def _check_playback(status: int, data: Optional[Dict[str, Any]]) -> None:
    _now_cache["at"] = 0  # the track probably changed: don't serve a stale "now playing"
    if status in (200, 202, 204):
        return
    reason = ((data or {}).get("error") or {}).get("reason", "")
    if status == 403 and reason == "PREMIUM_REQUIRED":
        raise SpotifyError("Playback control needs Spotify Premium.")
    if status == 404:
        raise SpotifyError("No Spotify device found. Open Spotify on your phone or computer first.")
    raise SpotifyError(f"Spotify playback error ({status}).")


# ---------------------------------------------------------------------------
# One-time login (PKCE)
# ---------------------------------------------------------------------------
def login() -> None:
    """Open the Spotify consent page, catch the redirect on 127.0.0.1 and store the token."""
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not client_id():
        raise SystemExit("Add SPOTIFY_CLIENT_ID to .env first.")

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result: Dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Tamagotchi is connected to Spotify &hearts; You can close this tab.</h2>".encode())

        def log_message(self, *args):  # keep the terminal quiet
            pass

    params = {
        "client_id": client_id(),
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "scope": SCOPES,
        "state": state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), Callback)
    print(f"Opening Spotify login... If the browser doesn't open, visit:\n{url}")
    webbrowser.open(url)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if result.get("state") != state or "code" not in result:
        raise SystemExit(f"Login failed: {result.get('error', 'state mismatch')}")
    data = _token_request(
        {
            "grant_type": "authorization_code",
            "code": result["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id(),
            "code_verifier": verifier,
        }
    )
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    _save_token(data)
    print(f"Done! Saved {TOKEN_FILE}.")


if __name__ == "__main__":
    login()
