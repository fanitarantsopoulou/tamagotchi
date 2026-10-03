"""Visual themes: preset registry, natural-language theme detection and persistence.

Flow for every chat message (see main.py):

    user message ──> detect()  ──is_theme_request?──yes──> save() ──> theme JSON to frontend
                         │
                         └──no──> normal chat flow (chat.reply), untouched

To add a new motif, add one entry to PRESETS (and optionally its decorations in
frontend/themes.js). The detection prompt and the JSON schema are generated from
PRESETS, so the recognition logic itself never needs to change.
"""

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal

import anthropic
from pydantic import BaseModel, Field

import storage

THEME_FILE = Path(__file__).resolve().parent / "data" / "theme.json"
MODEL = "claude-haiku-4-5"  # small, fast model is plenty for classification
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LOCK = threading.Lock()


@dataclass(frozen=True)
class Preset:
    """A predefined motif the frontend knows how to decorate."""

    label: str  # short Greek keyword shown to the user
    when: str  # when the model should pick it (goes into the detection prompt)
    colors: List[str]  # fallback palette: [main, accent, deep]
    reply: str  # what the pet says after switching to it


# ---------------------------------------------------------------------------
# Preset registry: the single place to add new motifs.
# ---------------------------------------------------------------------------
PRESETS: Dict[str, Preset] = {
    "default": Preset(
        label="classic",
        when="ONLY when the user explicitly wants the original/normal look back (reset)",
        colors=["#ffb3d4", "#e0408f", "#9c1f5f"],
        reply="Γύρισα στο κλασικό μου ροζ look, girl!",
    ),
    "custom": Preset(
        label="custom",
        when="any other new look: specific colors ('μωβ με χρυσό'), 'άλλαξε outfit', a vibe not listed here",
        colors=["#c3a6ff", "#7b5cd6", "#3b2a6b"],
        reply="Νέο look, νέα εγώ! Πώς σου φαίνομαι;",
    ),
    "christmas": Preset(
        label="christmas",
        when="Christmas, New Year, winter holidays",
        colors=["#d62839", "#f2c14e", "#1f5e35"],
        reply="OMG, Christmas mood ενεργοποιήθηκε! Στολίδια παντού!",
    ),
    "party": Preset(
        label="party",
        when="birthdays, parties, nights out, celebrations (not Christmas)",
        colors=["#ff4ecd", "#7b2ff7", "#2d0a4e"],
        reply="Party time, bestie! Κομφετί και glitter παντού!",
    ),
    "summer": Preset(
        label="summer",
        when="summer, beach, holidays by the sea, hot sunny days",
        colors=["#ffd166", "#06d6a0", "#118ab2"],
        reply="Summer vibes! Μόνο η παραλία μας λείπει, girl!",
    ),
    "happy": Preset(
        label="happy",
        when="cheerful, bright, energetic, 'something happier'",
        colors=["#ffd23f", "#ff7ab6", "#3bceac"],
        reply="Yay, χαρούμενα χρώματα! Νιώθω ήλιος, bestie!",
    ),
    "rainy": Preset(
        label="rainy",
        when="rain, storms, grey or gloomy weather, melancholy",
        colors=["#9fb3c8", "#5b7c99", "#2f4858"],
        reply="Βροχούλα έξω, βροχούλα και σε μένα. Πολύ aesthetic!",
    ),
    "cozy": Preset(
        label="cozy",
        when="cozy, warm, autumn, relaxed evenings, coffee, blankets",
        colors=["#e9c46a", "#c8553d", "#5e3023"],
        reply="Cozy vibes on. Κουβερτούλα και ζεστό ρόφημα, τέλειο!",
    ),
    "casual": Preset(
        label="casual",
        when="casual, relaxed, everyday, chill, weekend",
        colors=["#a8dadc", "#f4a261", "#264653"],
        reply="Chill και casual, όπως μου αρέσει!",
    ),
    "athletic": Preset(
        label="athletic",
        when="sporty, gym, workout, running, athleisure",
        colors=["#c6ff00", "#00b4d8", "#1b263b"],
        reply="Gym mode on! Πάμε για workout, bestie!",
    ),
    "office": Preset(
        label="office",
        when="work, office, studying, focus, business-like",
        colors=["#d9dde3", "#4a6fa5", "#2b2d42"],
        reply="Office mode on. Σοβαρή και productive, girlboss!",
    ),
    "formal": Preset(
        label="formal",
        when="formal, elegant, gala, wedding, black tie, classy",
        colors=["#3a3540", "#c9a227", "#121014"],
        reply="Black tie και χρυσό. So classy, darling!",
    ),
    "halloween": Preset(
        label="halloween",
        when="Halloween, spooky, scary, witches, pumpkins",
        colors=["#ff7518", "#6a0dad", "#1a0f1f"],
        reply="Boo! Spooky season, bestie!",
    ),
}

DEFAULT_THEME = {"motif": "default", "colors": PRESETS["default"].colors}

# The model may only answer with one of the registered motifs.
Motif = Literal[tuple(PRESETS)]  # type: ignore[valid-type]


class ThemeDecision(BaseModel):
    """The structured answer the detection step must return (enforced by structured outputs)."""

    is_theme_request: bool = Field(description="True only if the user asks to change the look/outfit/colors/theme.")
    colors: List[str] = Field(description="2-3 hex colors like #aabbcc for the new look: [main, accent, deep]. Empty if not a theme request.")
    motif: Motif = Field(description="The best matching motif keyword.")


NOT_A_THEME = ThemeDecision(is_theme_request=False, colors=[], motif="default")


def _detection_prompt() -> str:
    """System prompt for the classifier, generated from PRESETS so new motifs need no code changes."""
    motifs = "\n".join(f'- "{key}" ({p.label}): {p.when}' for key, p in PRESETS.items())
    return f"""You classify messages sent to a virtual pet app. Decide if the message asks to change \
the pet's look: its outfit, colors, style or theme (e.g. "άλλαξε outfit", "βάλε κάτι πιο \
χαρούμενο", "βάλε κάτι χριστουγεννιάτικο", "σήμερα βρέχει, βάλε κάτι αντίστοιχο", "go back to \
normal colors").

Questions, chatting, or asking for clothes/makeup advice for the USER are NOT theme requests.

If it is a theme request:
- pick the closest motif:
{motifs}
- choose 2-3 hex colors that fit the request, ordered [main, accent, deep]; the deep one must be \
dark enough to draw the pet on a light screen.

If it is not a theme request: is_theme_request=false, colors=[], motif="default"."""


def detect(message: str) -> ThemeDecision:
    """Ask the model whether `message` is a theme request. Returns a validated ThemeDecision."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return NOT_A_THEME  # no key: let the normal chat flow report the problem
    response = anthropic.Anthropic().messages.parse(
        model=MODEL,
        max_tokens=512,
        system=_detection_prompt(),
        messages=[{"role": "user", "content": message}],
        output_format=ThemeDecision,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return NOT_A_THEME
    return response.parsed_output


def _clean_colors(colors: List[str], motif: str) -> List[str]:
    """Keep only valid hex colors (max 3); fall back to the preset palette if fewer than 2."""
    valid = [c.lower() for c in colors if HEX.match(c)][:3]
    return valid if len(valid) >= 2 else PRESETS[motif].colors


def load() -> Dict[str, Any]:
    """The current theme, or the default one if none was saved."""
    if not THEME_FILE.exists():
        return dict(DEFAULT_THEME)
    theme = json.loads(THEME_FILE.read_text())
    return theme if theme.get("motif") in PRESETS else dict(DEFAULT_THEME)


def save(decision: ThemeDecision) -> Dict[str, Any]:
    """Persist a detected theme so it survives page refreshes; returns what was stored."""
    if decision.motif == "default":
        return reset()
    theme = {"motif": decision.motif, "colors": _clean_colors(decision.colors, decision.motif)}
    with LOCK:
        storage.write_json(THEME_FILE, theme)
    return theme


def reset() -> Dict[str, Any]:
    """Go back to the default look (manual reset or 'back to normal' in chat)."""
    with LOCK:
        THEME_FILE.unlink(missing_ok=True)
    return dict(DEFAULT_THEME)


def presets() -> List[Dict[str, Any]]:
    """The motifs a user can pick by hand (for the outfit list). 'custom' is chat-only."""
    return [{"motif": key, "label": p.label, "colors": p.colors} for key, p in PRESETS.items() if key != "custom"]


def set_preset(motif: str) -> Dict[str, Any]:
    """Switch to a preset picked from the outfit list (uses the preset's own palette)."""
    if motif not in PRESETS or motif == "custom":
        raise ValueError(f"Unknown outfit: {motif}")
    return save(ThemeDecision(is_theme_request=True, colors=PRESETS[motif].colors, motif=motif))


def reply_for(theme: Dict[str, Any]) -> str:
    """The pet's short confirmation after a theme change."""
    return PRESETS[theme["motif"]].reply
