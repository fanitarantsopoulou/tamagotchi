"""Read-only Google Calendar access: upcoming events from all of the user's calendars.

    agenda(start=None, days=1) -> list of {date, events: [...]}

Only titles, times and locations are returned (no descriptions or attendees), results are cached
for a few minutes, and API calls have a timeout. Problems raise CalendarUnavailable.
"""

import os
import threading
import time
from datetime import date as Date
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import google_auth

TIMEZONE = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))
TIMEOUT_SECONDS = 10
CACHE_TTL = 5 * 60
MAX_DAYS = 14

_cache: Dict[tuple, tuple] = {}
_cache_lock = threading.Lock()


class CalendarUnavailable(Exception):
    """The calendar couldn't be read (not logged in, login expired, network...)."""


def is_configured() -> bool:
    """True once the Google login has been done."""
    return google_auth.is_configured()


def _service():
    """A Calendar API client using the shared Google login, with a request timeout."""
    try:
        creds = google_auth.credentials()
    except google_auth.GoogleAuthError as e:
        raise CalendarUnavailable(str(e)) from e
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=TIMEOUT_SECONDS))
    return build("calendar", "v3", http=http, cache_discovery=False)


def _event(item: Dict[str, Any], calendar: str) -> Dict[str, Any]:
    """Keep only what's useful (and not too private) from a Calendar API event."""
    start, end = item.get("start", {}), item.get("end", {})
    all_day = "date" in start
    event = {
        "title": item.get("summary") or "(no title)",
        "calendar": calendar,
        "all_day": all_day,
        "start": start.get("date") if all_day else start.get("dateTime", "")[11:16],
        "end": None if all_day else end.get("dateTime", "")[11:16],
    }
    if item.get("location"):
        event["location"] = item["location"]
    return event


def _fetch(start: Date, days: int) -> List[Dict[str, Any]]:
    """Events from every calendar between start and start+days, grouped per day."""
    service = _service()
    time_min = datetime.combine(start, datetime.min.time(), TIMEZONE)
    time_max = time_min + timedelta(days=days)
    by_day: Dict[str, List[Dict[str, Any]]] = {(start + timedelta(days=i)).isoformat(): [] for i in range(days)}
    try:
        calendars = service.calendarList().list().execute().get("items", [])
        for cal in calendars:
            items = service.events().list(
                calendarId=cal["id"],
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,  # expand recurring events
                orderBy="startTime",
                maxResults=100,
            ).execute().get("items", [])
            for item in items:
                event = _event(item, cal.get("summaryOverride") or cal.get("summary", ""))
                start_info = item.get("start", {})
                day = start_info.get("date") or start_info.get("dateTime", "")[:10]
                # all-day events can span several days: list them on each day they cover
                if event["all_day"]:
                    end_day = Date.fromisoformat(item["end"]["date"])
                    d = Date.fromisoformat(day)
                    while d < end_day:
                        if d.isoformat() in by_day:
                            by_day[d.isoformat()].append(event)
                        d += timedelta(days=1)
                elif day in by_day:
                    by_day[day].append(event)
    except (HttpError, OSError, httplib2.HttpLib2Error) as e:
        raise CalendarUnavailable(f"calendar service error ({e.__class__.__name__})") from e

    # all-day first, then by start time
    return [
        {"date": day, "events": sorted(events, key=lambda e: (not e["all_day"], e["start"] or ""))}
        for day, events in by_day.items()
    ]


def agenda(start: Optional[str] = None, days: int = 1) -> List[Dict[str, Any]]:
    """Events for `days` days from `start` (YYYY-MM-DD, default today), cached for a few minutes."""
    try:
        first = Date.fromisoformat(start) if start else datetime.now(TIMEZONE).date()
    except ValueError:
        raise CalendarUnavailable(f"bad date: {start} (use YYYY-MM-DD)")
    days = max(1, min(days, MAX_DAYS))
    key = (first.isoformat(), days)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    result = _fetch(first, days)
    with _cache_lock:
        _cache[key] = (time.time(), result)
    return result
