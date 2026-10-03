"""Registry of context providers the chat can use.

To add a new source (e.g. Google Calendar): write a ContextProvider subclass in its own module
and add an instance to PROVIDERS. To remove one, delete it from the list. The chat itself only
calls tools() and prompt() below.
"""

from typing import List

from context_providers.base import ContextProvider
from context_providers.calendar import CalendarProvider
from context_providers.weather import WeatherProvider

PROVIDERS: List[ContextProvider] = [
    WeatherProvider(),
    CalendarProvider(),
]


def _enabled() -> List[ContextProvider]:
    return [p for p in PROVIDERS if p.is_enabled()]


def tools() -> List:
    """All tools from the enabled providers."""
    return [tool for p in _enabled() for tool in p.tools()]


def prompt() -> str:
    """All prompt sections from the enabled providers."""
    return "".join(p.prompt() for p in _enabled())
