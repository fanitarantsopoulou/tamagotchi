"""Calendar reminders: a heads-up shortly before each event (only when there is one)."""

from datetime import datetime, timedelta
from typing import List

import calendar_reader
import settings
from notification_providers.base import Notice, NotificationProvider

DEFAULT_LEAD_MINUTES = 30


class CalendarEventsProvider(NotificationProvider):
    name = "calendar"

    def is_enabled(self) -> bool:
        return calendar_reader.is_configured()

    def check(self, now: datetime) -> List[Notice]:
        lead = int(settings.get("notifications").get("calendar_lead_minutes", DEFAULT_LEAD_MINUTES))
        try:
            today = calendar_reader.agenda(now.date().isoformat(), 1)[0]
        except calendar_reader.CalendarUnavailable:
            return []  # the notifier logs nothing: no calendar, no reminders

        notices = []
        for event in today["events"]:
            if event["all_day"]:
                continue  # all-day events go into the morning digest instead
            start = datetime.combine(now.date(), datetime.strptime(event["start"], "%H:%M").time(), now.tzinfo)
            if now < start <= now + timedelta(minutes=lead):
                minutes = max(1, round((start - now).total_seconds() / 60))
                where = f" ({event['location']})" if event.get("location") else ""
                notices.append(
                    Notice(
                        key=f"cal-{today['date']}-{event['start']}-{event['title']}",
                        text=f"📅 Σε {minutes}' έχεις «{event['title']}» στις {event['start']}{where}. "
                        "Θες ιδέα για outfit; Γράψε μου στο chat!",
                        cooldown_hours=24,
                    )
                )
        return notices
