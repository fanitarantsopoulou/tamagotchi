"""Weather service: Open-Meteo forecast (free, no API key) turned into a compact summary.

    summary(city=None, day=None) -> dict
        city  defaults to the one in config/settings.json
        day   YYYY-MM-DD, defaults to today (in the city's own time zone)

Results are cached (forecasts 30 min, geocoding 24 h) and every HTTP call has a timeout.
Failures raise WeatherUnavailable so callers can carry on without weather.
"""

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date as Date
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import settings

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 5
FORECAST_TTL = 30 * 60
GEOCODE_TTL = 24 * 60 * 60
FORECAST_DAYS = 14

# Parts of the day, as [start hour, end hour) in local time.
DAY_PARTS = {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 24)}

# WMO weather codes -> short descriptions (https://open-meteo.com/en/docs, "WMO Weather interpretation codes").
WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers", 85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


# WMO codes -> one of a few pixel icons the frontend draws.
def icon_of(code: Optional[int]) -> str:
    """Map a weather code to an icon name: clear, partly, cloudy, fog, rain, snow, storm."""
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly"
    if code in (45, 48):
        return "fog"
    if code is not None and 95 <= code <= 99:
        return "storm"
    if code is not None and (71 <= code <= 77 or code in (85, 86)):
        return "snow"
    if code is not None and (51 <= code <= 67 or 80 <= code <= 82):
        return "rain"
    return "cloudy"


class WeatherUnavailable(Exception):
    """The weather couldn't be fetched (network, unknown city, date out of range...)."""


# ---------------------------------------------------------------------------
# Tiny thread-safe TTL cache
# ---------------------------------------------------------------------------
_cache: Dict[Tuple, Tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _cached(key: Tuple, ttl: int, fetch):
    """Return a fresh cached value for `key`, or call `fetch()` and cache its result."""
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = fetch()  # outside the lock: slow network calls shouldn't block other lookups
    with _cache_lock:
        _cache[key] = (time.time(), value)
    return value


def _get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET a JSON document with a timeout; any failure becomes WeatherUnavailable."""
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=TIMEOUT_SECONDS) as response:
            data = json.load(response)
    except (OSError, ValueError) as e:  # URLError, timeouts and bad JSON all land here
        raise WeatherUnavailable(f"weather service unreachable ({e.__class__.__name__})") from e
    if data.get("error"):
        raise WeatherUnavailable(data.get("reason", "weather service error"))
    return data


# ---------------------------------------------------------------------------
# Open-Meteo calls
# ---------------------------------------------------------------------------
def geocode(city: str, country_code: Optional[str] = None) -> Dict[str, Any]:
    """City name -> {name, country, latitude, longitude, timezone} (cached for a day)."""

    def fetch():
        params = {"name": city, "count": 1, "language": "en", "format": "json"}
        if country_code:
            params["countryCode"] = country_code
        results = _get_json(GEOCODING_URL, params).get("results") or []
        if not results:
            raise WeatherUnavailable(f"unknown city: {city}")
        r = results[0]
        return {k: r.get(k) for k in ("name", "country", "latitude", "longitude", "timezone")}

    return _cached(("geocode", city.lower(), country_code), GEOCODE_TTL, fetch)


def _forecast(lat: float, lon: float) -> Dict[str, Any]:
    """Raw Open-Meteo forecast for a location (cached for 30 minutes)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,relative_humidity_2m,"
        "wind_speed_10m,uv_index",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
        "wind_speed_10m_max,uv_index_max",
        "timezone": "auto",
        "forecast_days": FORECAST_DAYS,
    }
    return _cached(("forecast", round(lat, 2), round(lon, 2)), FORECAST_TTL, lambda: _get_json(FORECAST_URL, params))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def _round(values: List[float]) -> Optional[float]:
    return round(mean(values), 1) if values else None


def _day_part(hourly: Dict[str, List], day: str, start: int, end: int) -> Optional[Dict[str, Any]]:
    """Average/max values for one part of a day from the hourly series."""
    idx = [i for i, t in enumerate(hourly["time"]) if t.startswith(day) and start <= int(t[11:13]) < end]
    if not idx:
        return None

    def pick(key):
        return [hourly[key][i] for i in idx if hourly[key][i] is not None]

    return {
        "temp_c": _round(pick("temperature_2m")),
        "feels_like_c": _round(pick("apparent_temperature")),
        "rain_chance_pct": max(pick("precipitation_probability"), default=None),
        "wind_kmh": _round(pick("wind_speed_10m")),
    }


def _place(city: Optional[str]) -> Dict[str, Any]:
    """The requested city, or the default one from config/settings.json."""
    if city:
        return geocode(city)
    cfg = settings.get("weather")
    if not cfg.get("city"):
        raise WeatherUnavailable("no default city in config/settings.json")
    return geocode(cfg["city"], cfg.get("country_code"))


def _summarize(place: Dict[str, Any], data: Dict[str, Any], day: str, today: str) -> Dict[str, Any]:
    """Build the compact summary for one day out of a raw forecast."""
    daily = data["daily"]
    if day not in daily["time"]:
        raise WeatherUnavailable(f"no forecast for {day} (available: {daily['time'][0]} to {daily['time'][-1]})")
    d = daily["time"].index(day)

    hourly = data["hourly"]
    humidity = [h for t, h in zip(hourly["time"], hourly["relative_humidity_2m"]) if t.startswith(day) and h is not None]
    code = daily["weather_code"][d]
    result = {
        "location": f"{place['name']}, {place['country']}",
        "date": day,
        "conditions": WEATHER_CODES.get(code, "unknown"),
        "icon": icon_of(code),
        "min_c": daily["temperature_2m_min"][d],
        "max_c": daily["temperature_2m_max"][d],
        "rain_chance_pct": daily["precipitation_probability_max"][d],
        "max_wind_kmh": daily["wind_speed_10m_max"][d],
        "avg_humidity_pct": _round(humidity),
        "uv_index_max": daily["uv_index_max"][d],
        "parts_of_day": {name: _day_part(hourly, day, *hours) for name, hours in DAY_PARTS.items()},
    }
    if day == today:
        cur = data["current"]
        result["now"] = {
            "temp_c": cur["temperature_2m"],
            "feels_like_c": cur["apparent_temperature"],
            "humidity_pct": cur["relative_humidity_2m"],
            "wind_kmh": cur["wind_speed_10m"],
            "conditions": WEATHER_CODES.get(cur["weather_code"], "unknown"),
            "icon": icon_of(cur["weather_code"]),
        }
    return result


def _today_in(place: Dict[str, Any]) -> str:
    return datetime.now(ZoneInfo(place["timezone"] or "UTC")).date().isoformat()


def summary(city: Optional[str] = None, day: Optional[str] = None) -> Dict[str, Any]:
    """A compact weather summary for one day in one city (defaults: settings city, today)."""
    place = _place(city)
    data = _forecast(place["latitude"], place["longitude"])
    today = _today_in(place)
    day = day or today
    try:
        Date.fromisoformat(day)
    except ValueError:
        raise WeatherUnavailable(f"bad date: {day} (use YYYY-MM-DD)")
    return _summarize(place, data, day, today)


def outlook(city: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
    """Summaries for today and the next days (one forecast call, shared cache)."""
    place = _place(city)
    data = _forecast(place["latitude"], place["longitude"])
    today = _today_in(place)
    upcoming = [d for d in data["daily"]["time"] if d >= today][: max(1, min(days, FORECAST_DAYS))]
    return [_summarize(place, data, d, today) for d in upcoming]
