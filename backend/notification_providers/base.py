"""The interface every notification source implements (pet, calendar, morning digest...).

A provider only *decides* what's worth saying right now; the notifier (notifier.py) takes care of
quiet hours, duplicates, daily limits, the in-app inbox and sending to Telegram.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional


@dataclass
class Notice:
    key: str  # stable id used to avoid repeats, e.g. "pet-hungry" or "cal-2026-10-05-10:00-Meeting"
    text: str = ""  # the message, in the pet's voice
    cooldown_hours: float = 24  # don't send the same key again within this time
    urgent: bool = False  # urgent notices ignore the daily limit
    # For expensive messages (e.g. written by the AI): called only if the notice will really be
    # sent, so a skipped duplicate costs nothing.
    make_text: Optional[Callable[[], str]] = None


class NotificationProvider:
    """Base class: subclass it and register an instance in notification_providers/__init__.py."""

    name = "base"

    def is_enabled(self) -> bool:
        return True

    def check(self, now: datetime) -> List[Notice]:
        """Return the notices worth sending right now (an empty list most of the time)."""
        return []
