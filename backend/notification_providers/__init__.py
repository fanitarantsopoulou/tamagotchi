"""Registry of notification sources. Add a provider here and the notifier starts checking it."""

from typing import List

from notification_providers.base import Notice, NotificationProvider
from notification_providers.calendar_events import CalendarEventsProvider
from notification_providers.morning_digest import MorningDigestProvider
from notification_providers.pet_care import PetCareProvider

PROVIDERS: List[NotificationProvider] = [
    PetCareProvider(),
    CalendarEventsProvider(),
    MorningDigestProvider(),
]

__all__ = ["Notice", "NotificationProvider", "PROVIDERS"]
