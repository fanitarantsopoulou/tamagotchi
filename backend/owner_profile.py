"""The owner's profile, set during onboarding: what to call them and the pet's personality.

Personalities are a registry like the theme presets: add an entry to PERSONALITIES and it shows up
in the onboarding wizard and shapes how the pet talks, with no other code changes.
"""

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import storage

PROFILE_FILE = Path(__file__).resolve().parent / "data" / "profile.json"
LOCK = threading.Lock()
MAX_NAME = 20


@dataclass(frozen=True)
class Personality:
    label: str  # shown in the wizard
    description: str  # one line for the wizard card
    style: str  # how the pet talks (goes into the chat's system prompt)
    greeting: str  # first chat line; {user} is replaced by the owner's name/nickname


PERSONALITIES: Dict[str, Personality] = {
    "sassy": Personality(
        label="Sassy bestie",
        description="90s/Y2K slang, playful and a little dramatic.",
        style="a fun Greek 90s/Y2K bestie, sprinkling in English slang the way Greek girls do: \"OMG\", "
        "\"girl\", \"bestie\", \"as if!\", \"so fetch\", \"κορίτσι μου\", \"τέλειο\", \"πεθαίνω\", \"σε λατρεύω\"",
        greeting="What's up {user}?",
    ),
    "sweet": Personality(
        label="Sweet & calm",
        description="Warm, gentle and encouraging. Little slang.",
        style="a warm, gentle and encouraging friend: soft words, calm tone, kind compliments, "
        "almost no slang and no drama",
        greeting="Γεια σου {user}, πώς είσαι σήμερα;",
    ),
    "hype": Personality(
        label="Hype coach",
        description="High energy, cheers you on, loves a challenge.",
        style="an energetic hype coach and cheerleader: upbeat, motivating, celebrates every small win, "
        "uses words like \"πάμε!\", \"let's go\", \"είσαι φωτιά\"",
        greeting="Let's go {user}! Τι κάνουμε σήμερα;",
    ),
    "witty": Personality(
        label="Witty & dry",
        description="Clever, deadpan humour, a bit sarcastic but kind.",
        style="a witty friend with dry, deadpan humour and light, never mean, sarcasm; clever one-liners, "
        "understated",
        greeting="Α, εσύ πάλι {user}. Καλώς την. Τι θέλουμε;",
    ),
}
DEFAULT_PROFILE = {"user_name": "girl", "personality": "sassy", "onboarded": False}


def load() -> Dict[str, Any]:
    """The saved profile, or defaults (the original sassy pet) before onboarding."""
    if not PROFILE_FILE.exists():
        return dict(DEFAULT_PROFILE)
    profile = {**DEFAULT_PROFILE, **json.loads(PROFILE_FILE.read_text())}
    if profile["personality"] not in PERSONALITIES:
        profile["personality"] = DEFAULT_PROFILE["personality"]
    return profile


def save(user_name: str, personality: str) -> Dict[str, Any]:
    """Store the onboarding answers."""
    if personality not in PERSONALITIES:
        raise ValueError(f"Unknown personality: {personality}")
    profile = {
        "user_name": user_name.strip()[:MAX_NAME] or DEFAULT_PROFILE["user_name"],
        "personality": personality,
        "onboarded": True,
        "onboarded_at": int(time.time()),
    }
    with LOCK:
        storage.write_json(PROFILE_FILE, profile)
    return profile


def personality() -> Personality:
    """The current personality (default: sassy)."""
    return PERSONALITIES[load()["personality"]]


def greeting() -> str:
    """The pet's first chat line, personalised with the owner's name."""
    p = load()
    return PERSONALITIES[p["personality"]].greeting.format(user=p["user_name"])


def options() -> List[Dict[str, str]]:
    """Personalities for the wizard (id, label, description)."""
    return [{"id": key, "label": p.label, "description": p.description} for key, p in PERSONALITIES.items()]
