"""The outfit the pet suggested today, so Mirror mode can compare a photo against it.

Only the latest suggestion of the current day is kept; older days are simply ignored.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import storage

SUGGESTION_FILE = Path(__file__).resolve().parent / "data" / "outfit_of_day.json"
TIMEZONE = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))
LOCK = threading.Lock()


def _today() -> str:
    """Today's date (local time) as YYYY-MM-DD."""
    return datetime.now(TIMEZONE).date().isoformat()


def save(summary: str, pieces: List[str], colors: List[str], style: str) -> Dict[str, Any]:
    """Store a new suggestion for today, replacing any earlier one."""
    suggestion = {
        "date": _today(),
        "saved_at": datetime.now(TIMEZONE).isoformat(timespec="minutes"),
        "summary": summary.strip(),
        "pieces": [p.strip() for p in pieces if p.strip()],
        "colors": [c.strip() for c in colors if c.strip()],
        "style": style.strip(),
    }
    with LOCK:
        storage.write_json(SUGGESTION_FILE, suggestion)
    return suggestion


def load_today() -> Optional[Dict[str, Any]]:
    """Today's suggestion, or None if the pet hasn't suggested an outfit today."""
    if not SUGGESTION_FILE.exists():
        return None
    suggestion = json.loads(SUGGESTION_FILE.read_text())
    return suggestion if suggestion.get("date") == _today() else None


def describe(suggestion: Dict[str, Any]) -> str:
    """A compact text version of a suggestion, for prompts."""
    lines = [f"Summary: {suggestion['summary']}"]
    if suggestion.get("pieces"):
        lines.append("Pieces: " + "; ".join(suggestion["pieces"]))
    if suggestion.get("colors"):
        lines.append("Colors: " + ", ".join(suggestion["colors"]))
    if suggestion.get("style"):
        lines.append(f"Style: {suggestion['style']}")
    return "\n".join(lines)
