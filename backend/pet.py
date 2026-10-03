"""Pet game logic: stats, time-based decay, actions and JSON persistence."""

import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import storage

DATA_FILE = Path(__file__).resolve().parent / "data" / "pet.json"
# Requests run in parallel threads; one load-change-save at a time keeps updates from being lost.
LOCK = threading.Lock()

# Rates are per minute. Tweak these to make the pet more or less demanding.
HUNGER_DECAY = 0.5
HAPPY_DECAY = 0.4
ENERGY_DECAY = 0.3
ENERGY_REGEN = 1.0
SLEEP_DECAY_FACTOR = 0.3  # hunger/happiness drop slower while asleep
HEALTH_DRAIN = 0.5
HEALTH_REGEN = 0.2
POOP_EVERY_MIN = 45
MAX_POOPS = 4

# Mood thresholds (stats are 0-100). See mood_of() for the priority order.
SICK_HEALTH = 50
SICK_POOPS = 3
HUNGRY_BELOW = 25
TIRED_BELOW = 20
SAD_BELOW = 25
HAPPY_ABOVE = 60

# (age in minutes it lasts until, stage name)
STAGES = [(1, "egg"), (60, "baby"), (24 * 60, "child"), (math.inf, "adult")]


class ActionError(ValueError):
    pass


def new_pet(name: str = "Mochi") -> Dict[str, Any]:
    """Create a fresh pet dict with starting stats, born right now."""
    now = time.time()
    return {
        "name": name,
        "born_at": now,
        "last_update": now,
        "hunger": 80.0,  # 100 = full, 0 = starving
        "happiness": 80.0,
        "energy": 100.0,
        "health": 100.0,
        "poops": 0,
        "poop_timer": 0.0,
        "sleeping": False,
        "alive": True,
    }


def _clamp(value: float) -> float:
    """Limit a stat value to the 0-100 range."""
    return max(0.0, min(100.0, value))


def stage_of(pet: Dict[str, Any], now: float) -> str:
    """Return the pet's life stage (egg/baby/child/adult) based on its age at `now`."""
    age_min = (now - pet["born_at"]) / 60
    for limit, name in STAGES:
        if age_min < limit:
            return name
    return STAGES[-1][1]


def _step(pet: Dict[str, Any], minutes: float) -> None:
    """Advance the simulation by at most one minute."""
    factor = SLEEP_DECAY_FACTOR if pet["sleeping"] else 1.0
    pet["hunger"] = _clamp(pet["hunger"] - HUNGER_DECAY * minutes * factor)
    pet["happiness"] = _clamp(pet["happiness"] - HAPPY_DECAY * minutes * factor)

    if pet["sleeping"]:
        pet["energy"] = _clamp(pet["energy"] + ENERGY_REGEN * minutes)
    else:
        pet["energy"] = _clamp(pet["energy"] - ENERGY_DECAY * minutes)
        pet["poop_timer"] += minutes
        if pet["poop_timer"] >= POOP_EVERY_MIN:
            pet["poop_timer"] -= POOP_EVERY_MIN
            pet["poops"] = min(MAX_POOPS, pet["poops"] + 1)

    neglected = pet["hunger"] == 0 or pet["happiness"] == 0 or pet["poops"] >= 3
    if neglected:
        pet["health"] = _clamp(pet["health"] - HEALTH_DRAIN * minutes)
    else:
        pet["health"] = _clamp(pet["health"] + HEALTH_REGEN * minutes)

    if pet["health"] == 0:
        pet["alive"] = False


def tick(pet: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
    """Catch the pet up to `now`, simulating minute by minute so long absences are fair."""
    now = now or time.time()
    elapsed = max(0.0, (now - pet["last_update"]) / 60)
    if pet["alive"] and stage_of(pet, now) != "egg":
        while elapsed > 0 and pet["alive"]:
            step = min(1.0, elapsed)
            _step(pet, step)
            elapsed -= step
    pet["last_update"] = now
    return pet


def mood_of(pet: Dict[str, Any], stage: str) -> str:
    """The pet's mood from its stats; the most urgent one wins when several apply."""
    if not pet["alive"]:
        return "dead"
    if stage == "egg":
        return "egg"
    if pet["sleeping"]:
        return "sleeping"
    if pet["health"] < SICK_HEALTH or pet["poops"] >= SICK_POOPS:
        return "sick"
    if pet["hunger"] < HUNGRY_BELOW:
        return "hungry"
    if pet["energy"] < TIRED_BELOW:
        return "tired"
    if pet["happiness"] < SAD_BELOW:
        return "sad"
    if min(pet["hunger"], pet["happiness"], pet["energy"], pet["health"]) > HAPPY_ABOVE:
        return "happy"
    return "ok"


def public_view(pet: Dict[str, Any]) -> Dict[str, Any]:
    """Build the API response: rounded stats plus derived stage, age, mood and attention flag."""
    now = time.time()
    view = {k: v for k, v in pet.items() if k != "poop_timer"}
    for key in ("hunger", "happiness", "energy", "health"):
        view[key] = round(pet[key])
    view["stage"] = stage_of(pet, now)
    view["mood"] = mood_of(pet, view["stage"])
    view["age_minutes"] = int((now - pet["born_at"]) // 60)
    view["needs_attention"] = pet["alive"] and (
        min(pet["hunger"], pet["happiness"], pet["energy"]) < 25 or pet["poops"] > 0
    )
    return view


def load() -> Dict[str, Any]:
    """Read the pet from disk (or create a new one) and catch it up to the current time."""
    if DATA_FILE.exists():
        pet = json.loads(DATA_FILE.read_text())
    else:
        pet = new_pet()
    return tick(pet)


def save(pet: Dict[str, Any]) -> None:
    """Write the pet to disk atomically via a temp file so a crash can't corrupt it."""
    storage.write_json(DATA_FILE, pet)


def get_state() -> Dict[str, Any]:
    """Load, update and save the pet, then return its public view."""
    with LOCK:
        pet = load()
        save(pet)
    return public_view(pet)


def reset(name: str) -> Dict[str, Any]:
    """Start a new pet with the given name (trimmed to 12 chars) and save it."""
    pet = new_pet(name.strip()[:12] or "Mochi")
    with LOCK:
        save(pet)
    return public_view(pet)


def perform(action: str) -> Dict[str, Any]:
    """Load the pet, apply an action, save it, and return the new state with an LCD message."""
    with LOCK:
        pet = load()
        message = _apply(pet, action)
        save(pet)
    return {"pet": public_view(pet), "message": message}


def _apply(pet: Dict[str, Any], action: str) -> str:
    """Change the pet's stats for one action and return the message; raise ActionError if not allowed."""
    # LCD fonts have no Greek glyphs, so on-screen messages stay in English.
    if not pet["alive"]:
        raise ActionError("R.I.P.")
    if stage_of(pet, time.time()) == "egg":
        raise ActionError("STILL AN EGG")

    if action == "sleep":
        pet["sleeping"] = not pet["sleeping"]
        return "GOOD NIGHT" if pet["sleeping"] else "GOOD MORNING"

    if pet["sleeping"]:
        raise ActionError("ZZZ...")

    if action == "feed":
        if pet["hunger"] >= 95:
            pet["happiness"] = _clamp(pet["happiness"] - 5)
            return "TOO FULL!"
        pet["hunger"] = _clamp(pet["hunger"] + 25)
        return "YUM!"

    if action == "play":
        if pet["energy"] < 10:
            raise ActionError("TOO TIRED")
        pet["happiness"] = _clamp(pet["happiness"] + 20)
        pet["energy"] = _clamp(pet["energy"] - 10)
        pet["hunger"] = _clamp(pet["hunger"] - 5)
        return "YAY!"

    if action == "clean":
        if pet["poops"] == 0:
            return "ALL CLEAN"
        pet["poops"] = 0
        return "SPARKLY!"

    raise ActionError(f"UNKNOWN: {action}")
