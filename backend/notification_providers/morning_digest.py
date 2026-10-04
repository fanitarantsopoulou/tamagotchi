"""Morning digest: once a day, the pet writes a short good-morning message.

It reuses the normal chat (same persona and tools), so it checks the weather and the calendar by
itself, mentions events only if there are any, and its outfit idea becomes today's suggestion for
Mirror mode. That's one or two Claude Haiku calls per day.
"""

from datetime import datetime, time, timedelta
from typing import List

import chat
import pet
import settings
from notification_providers.base import Notice, NotificationProvider

DEFAULT_TIME = "08:30"
WINDOW_HOURS = 4  # if the Mac was asleep at digest time, still send it within this window

DIGEST_REQUEST = (
    "Γράψε μου την πρωινή μου σύνοψη για σήμερα σε 2-4 σύντομες προτάσεις: πες καλημέρα, "
    "πες μου πώς θα είναι ο καιρός, ανέφερε τα σημερινά μου events από το ημερολόγιο ΜΟΝΟ αν "
    "υπάρχουν, και πρότεινέ μου ένα outfit από τη ντουλάπα μου."
)


class MorningDigestProvider(NotificationProvider):
    name = "digest"

    def check(self, now: datetime) -> List[Notice]:
        hh, mm = (int(x) for x in settings.get("notifications").get("digest_time", DEFAULT_TIME).split(":"))
        due = datetime.combine(now.date(), time(hh, mm), now.tzinfo)
        if not (due <= now < due + timedelta(hours=WINDOW_HOURS)):
            return []
        if not pet.get_state()["alive"]:
            return []  # the pet-care provider already says what happened
        return [Notice(key=f"digest-{now.date().isoformat()}", make_text=_write_digest, cooldown_hours=20, urgent=True)]


def _write_digest() -> str:
    """Ask the pet (normal chat, with its tools) for today's digest; empty string if the AI is unavailable."""
    try:
        return "☀️ " + chat.reply([{"role": "user", "content": DIGEST_REQUEST}], pet.get_state())["message"]
    except chat.ChatError:
        return ""
