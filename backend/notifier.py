"""The notification engine: checks every provider every few minutes and delivers what's new.

    providers decide WHAT to say  ->  notifier decides WHETHER and WHERE
                                      (quiet hours, repeats, daily limit, inbox, Telegram)

State lives in data/notifications.json: when each notice key was last sent (to avoid repeats)
and an inbox of recent notices that the app's NOTIFS.EXE window shows.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from datetime import time as Time
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import settings
import storage
import telegram_client
from notification_providers import PROVIDERS, Notice

STATE_FILE = Path(__file__).resolve().parent / "data" / "notifications.json"
TIMEZONE = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))
CHECK_EVERY_SECONDS = 5 * 60
INBOX_SIZE = 50
DEFAULTS = {"quiet_hours": ["23:00", "08:00"], "max_per_day": 10}

log = logging.getLogger("notifier")
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def _load() -> Dict[str, Any]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"sent": {}, "inbox": [], "per_day": {}}


def inbox() -> List[Dict[str, Any]]:
    """Recent notices, newest first (for the NOTIFS.EXE window)."""
    return _load()["inbox"]


def _config() -> Dict[str, Any]:
    return {**DEFAULTS, **settings.get("notifications")}


def _in_quiet_hours(now: datetime) -> bool:
    """Whether now falls in the quiet window (which may wrap past midnight, e.g. 23:00-08:00)."""
    start, end = (Time.fromisoformat(t) for t in _config()["quiet_hours"])
    t = now.time()
    return start <= t < end if start < end else (t >= start or t < end)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def _deliver(state: Dict[str, Any], notice: Notice, text: str, now: datetime) -> None:
    """Add to the inbox and send to Telegram (if set up); a Telegram failure doesn't lose the notice."""
    sent_to_phone = False
    if telegram_client.is_configured():
        try:
            telegram_client.send(text)
            sent_to_phone = True
        except telegram_client.TelegramError as e:
            log.warning("Telegram send failed: %s", e)
    state["inbox"].insert(0, {"at": now.isoformat(timespec="minutes"), "key": notice.key, "text": text, "telegram": sent_to_phone})
    del state["inbox"][INBOX_SIZE:]
    state["sent"][notice.key] = time.time()
    day = now.date().isoformat()
    state["per_day"] = {day: state["per_day"].get(day, 0) + 1}  # keep only today's counter


def run_once(now: datetime = None) -> List[str]:
    """One check of every provider; returns the texts that were delivered."""
    now = now or datetime.now(TIMEZONE)
    if _in_quiet_hours(now):
        return []  # nothing is marked as sent, so anything still relevant goes out after quiet hours

    delivered = []
    with _lock:
        state = _load()
        for provider in PROVIDERS:
            if not provider.is_enabled():
                continue
            try:
                notices = provider.check(now)
            except Exception:  # one broken source mustn't stop the others
                log.exception("Notification provider %s failed", provider.name)
                continue
            for notice in notices:
                last = state["sent"].get(notice.key)
                if last and time.time() - last < notice.cooldown_hours * 3600:
                    continue  # already told you
                if not notice.urgent and state["per_day"].get(now.date().isoformat(), 0) >= _config()["max_per_day"]:
                    continue  # enough for today
                text = notice.make_text() if notice.make_text else notice.text
                if not text:
                    continue
                _deliver(state, notice, text, now)
                delivered.append(text)
        storage.write_json(STATE_FILE, state)
    return delivered


def send_test() -> Dict[str, Any]:
    """Send a test message right away (ignores quiet hours); used by the NOTIFS.EXE test button."""
    now = datetime.now(TIMEZONE)
    with _lock:
        state = _load()
        notice = Notice(key=f"test-{time.time()}", text="🔔 Test από το Tamagotchi σου! Αν το βλέπεις στο Telegram, όλα δουλεύουν.")
        _deliver(state, notice, notice.text, now)
        storage.write_json(STATE_FILE, state)
    return state["inbox"][0]


def loop_forever(stop: threading.Event) -> None:
    """Background loop started with the server (see main.py)."""
    while not stop.is_set():
        try:
            run_once()
        except Exception:
            log.exception("Notifier run failed")
        stop.wait(CHECK_EVERY_SECONDS)
