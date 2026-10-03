"""User settings from config/settings.json (location etc.), kept out of the code.

The file is read on every call, so edits apply without restarting the server.
"""

import json
from pathlib import Path
from typing import Any, Dict

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "config" / "settings.json"


def load() -> Dict[str, Any]:
    """All settings, or an empty dict if the file is missing or broken."""
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def get(section: str) -> Dict[str, Any]:
    """One settings section, e.g. get("weather") -> {"city": "Athens", ...}."""
    value = load().get(section)
    return value if isinstance(value, dict) else {}
