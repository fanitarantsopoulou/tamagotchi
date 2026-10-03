"""Weather context provider: lets the pet check the real forecast before suggesting outfits/makeup."""

import json
from typing import List, Optional

from anthropic import beta_tool

import settings
import weather
from context_providers.base import ContextProvider

WEATHER_PROMPT = """
Weather (get_weather tool):
- Before suggesting an outfit or makeup, call get_weather (default city; pass city and/or date \
for other places or days, e.g. a trip to Θεσσαλονίκη on Saturday -> city="Thessaloniki", date=that \
Saturday as YYYY-MM-DD). Also use it for plain weather questions.
- Adapt to it, always using only items from the closet list:
  - big gap between morning and evening temperatures -> layers;
  - rain chance -> something waterproof / suitable shoes; wind -> avoid flowy pieces, mention it;
  - heat -> light, breathable fabrics;
  - makeup: humidity or rain -> long-wear / waterproof products and setting spray if they own it; \
high UV (6+) -> remind sunscreen; heat -> light textures.
- Mention the weather naturally in a few words, not like a forecast bulletin, and don't announce \
that you're checking it ("let me check the weather...") - just answer.
- If get_weather says the weather is unavailable, say you couldn't check it and give a suggestion \
anyway. Never make up weather."""


class WeatherProvider(ContextProvider):
    """Exposes get_weather; enabled when a default city is set in config/settings.json."""

    name = "weather"

    def is_enabled(self) -> bool:
        return bool(settings.get("weather").get("city"))

    def prompt(self) -> str:
        return WEATHER_PROMPT

    def tools(self) -> List:
        @beta_tool
        def get_weather(city: Optional[str] = None, date: Optional[str] = None) -> str:
            """Get a compact weather summary: now (if today), min/max, morning/afternoon/evening,
            rain chance, wind, humidity and UV.

            Args:
                city: City name, only for somewhere other than your bestie's home city.
                date: Day as YYYY-MM-DD, only if not today (forecasts go up to ~2 weeks ahead).
            """
            try:
                return json.dumps(weather.summary(city, date), ensure_ascii=False)
            except weather.WeatherUnavailable as e:
                # a normal (non-error) answer, so the model just carries on without weather
                return f"Weather unavailable: {e}. Don't guess the weather."

        return [get_weather]
