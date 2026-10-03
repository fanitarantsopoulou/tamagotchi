"""Telegram: the pet sends you messages through your own bot.

Setup (once):
  1. In Telegram, talk to @BotFather -> /newbot, and put the token in .env as TELEGRAM_BOT_TOKEN.
  2. Open your new bot and send it /start.
  3. On the Mac run:  .venv/bin/python backend/telegram_client.py
     It finds your chat and saves its id in secrets/telegram_chat.json, so messages only ever go
     to you.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

CHAT_FILE = Path(__file__).resolve().parent.parent / "secrets" / "telegram_chat.json"
API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT_SECONDS = 10
MAX_LENGTH = 4000  # Telegram's limit is 4096 characters per message


class TelegramError(Exception):
    """Sending failed (not set up, network, Telegram error)."""


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def chat_id() -> Optional[int]:
    if not CHAT_FILE.exists():
        return None
    return json.loads(CHAT_FILE.read_text()).get("chat_id")


def is_configured() -> bool:
    """True once there's a bot token and the chat has been linked."""
    return bool(_token()) and chat_id() is not None


def _call(method: str, params: Dict[str, Any]) -> Any:
    """Call a Bot API method; returns its "result" or raises TelegramError."""
    if not _token():
        raise TelegramError("TELEGRAM_BOT_TOKEN is missing from .env.")
    url = API.format(token=_token(), method=method)
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=TIMEOUT_SECONDS) as res:
            body = json.load(res)
    except urllib.error.HTTPError as e:
        try:
            body = json.load(e)
        except ValueError:
            raise TelegramError(f"Telegram error {e.code}") from e
    except (OSError, ValueError) as e:  # network problems, timeouts, bad JSON
        raise TelegramError(f"Telegram unreachable ({e.__class__.__name__})") from e
    if not body.get("ok"):
        raise TelegramError(body.get("description", "Telegram error"))
    return body["result"]


def send(text: str) -> None:
    """Send a plain-text message to the linked chat."""
    target = chat_id()
    if target is None:
        raise TelegramError("Telegram chat isn't linked yet. Run: .venv/bin/python backend/telegram_client.py")
    _call("sendMessage", {"chat_id": target, "text": text[:MAX_LENGTH], "disable_web_page_preview": "true"})


def link() -> None:
    """Find the chat that sent /start to the bot and remember it."""
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not _token():
        raise SystemExit("Add TELEGRAM_BOT_TOKEN to .env first (from @BotFather).")
    me = _call("getMe", {})
    updates = _call("getUpdates", {"timeout": 0})
    chats = [u["message"]["chat"] for u in updates if u.get("message", {}).get("chat", {}).get("type") == "private"]
    if not chats:
        raise SystemExit(f"No messages yet. Open t.me/{me['username']} in Telegram, send /start, then run this again.")
    chat = chats[-1]
    CHAT_FILE.parent.mkdir(exist_ok=True)
    CHAT_FILE.write_text(json.dumps({"chat_id": chat["id"], "first_name": chat.get("first_name", "")}))
    CHAT_FILE.chmod(0o600)
    os.environ["TELEGRAM_BOT_TOKEN"] = _token()
    send("Hey bestie! 🥚 Your TAMA SMART is connected. I'll ping you here.")
    print(f"Linked @{me['username']} to your chat and sent a hello message.")


if __name__ == "__main__":
    link()
