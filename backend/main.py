import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Literal

import anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import calendar_reader
import chat
from library import routes as library_routes
from memory import routes as memory_routes
import mirror
import notifier
import outfit_of_day
import pet
import owner_profile
import spotify_client
import theme
import weather

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run the notifier in a background thread for as long as the server is up."""
    stop = threading.Event()
    threading.Thread(target=notifier.loop_forever, args=(stop,), daemon=True, name="notifier").start()
    yield
    stop.set()


app = FastAPI(title="Smart Tamagotchi", lifespan=lifespan)


@app.middleware("http")
async def no_stale_frontend(request, call_next):
    """Make browsers revalidate the frontend files on every load, so updates show up without a hard refresh."""
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class ResetRequest(BaseModel):
    name: str = "Mochi"


@app.get("/api/pet")
def get_pet():
    """Return the pet's current state, updated to the present moment."""
    return pet.get_state()


@app.post("/api/pet/{action}")
def pet_action(action: str):
    """Run a game action on the pet; rule violations become a 400 with the LCD message."""
    try:
        return pet.perform(action)
    except pet.ActionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/reset")
def reset_pet(body: ResetRequest):
    """Replace the current pet with a brand-new egg, keeping the given name."""
    return pet.reset(body.name)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)  # long enough to paste a note to save


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


@app.get("/api/chat/greeting")
def chat_greeting():
    """Return the line the pet opens every chat with."""
    return {"message": chat.greeting()}


@app.post("/api/chat")
def chat_message(body: ChatRequest):
    """Reply to the chat as the pet.

    Step 1: a small classifier call checks whether the latest message asks for a new look.
            If so, the theme is saved and returned, and the normal chat is skipped.
    Step 2: otherwise the message goes through the normal chat flow, unchanged.
    """
    history = [m.model_dump() for m in body.messages]

    latest = history[-1]["content"] if history and history[-1]["role"] == "user" else ""
    if latest:
        try:
            decision = theme.detect(latest)
        except anthropic.AnthropicError:
            decision = None  # detection is best-effort; the chat flow below reports real API problems
        if decision and decision.is_theme_request:
            saved = theme.save(decision)
            label = theme.PRESETS[saved["motif"]].label
            return {"message": theme.reply_for(saved), "changes": [f"theme: {label}"], "theme": saved}

    try:
        return chat.reply(history, pet.get_state())
    except chat.ChatError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/theme")
def get_theme():
    """Return the active theme (motif + colors) so the frontend can restore it after a refresh."""
    return theme.load()


class ThemePick(BaseModel):
    motif: str


@app.get("/api/theme/presets")
def theme_presets():
    """List the outfits the user can pick by hand (built from the preset registry)."""
    return theme.presets()


@app.put("/api/theme")
def pick_theme(body: ThemePick):
    """Apply an outfit chosen from the outfit list."""
    try:
        return theme.set_preset(body.motif)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/theme")
def reset_theme():
    """Manually reset to the default look."""
    return theme.reset()


# ---------- Onboarding / profile ----------
class OnboardingAnswers(BaseModel):
    pet_name: str = Field(min_length=1, max_length=12)
    user_name: str = Field(min_length=1, max_length=owner_profile.MAX_NAME)
    personality: str


@app.get("/api/profile")
def get_profile():
    """The owner's profile (has onboarding been done?) and the personalities to choose from."""
    return {**owner_profile.load(), "pet_name": pet.get_state()["name"], "personalities": owner_profile.options()}


@app.post("/api/onboarding")
def finish_onboarding(body: OnboardingAnswers):
    """Save the onboarding answers and name the pet (a dead pet is replaced by a new egg)."""
    try:
        saved = owner_profile.save(body.user_name, body.personality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    current = pet.get_state()
    new_pet = pet.rename(body.pet_name) if current["alive"] else pet.reset(body.pet_name)
    return {"profile": saved, "pet": new_pet}


# ---------- Notifications ----------
@app.get("/api/notifications")
def get_notifications():
    """Recent notifications (the in-app inbox) and whether Telegram is connected."""
    import telegram_client

    return {"telegram": telegram_client.is_configured(), "inbox": notifier.inbox()}


@app.post("/api/notifications/test")
def test_notification():
    """Send a test notification now (to the inbox and, if connected, to Telegram)."""
    return notifier.send_test()


# ---------- Weather ----------
@app.get("/api/weather")
def get_weather(city: str = "", days: int = 7):
    """Today + upcoming days for a city (default city from config/settings.json)."""
    try:
        return {"days": weather.outlook(city.strip() or None, days)}
    except weather.WeatherUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- Calendar ----------
@app.get("/api/calendar")
def get_calendar(days: int = 7):
    """Events for today and the next days, grouped per day (read-only Google Calendar)."""
    if not calendar_reader.is_configured():
        raise HTTPException(status_code=404, detail="Calendar isn't connected yet.")
    try:
        return {"days": calendar_reader.agenda(None, days)}
    except calendar_reader.CalendarUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------- Spotify (walkman) ----------
@app.get("/api/spotify/now-playing")
def spotify_now_playing():
    """What's playing right now, for the walkman on the page."""
    if not spotify_client.is_configured():
        return {"configured": False, "track": None}
    try:
        return {"configured": True, "track": spotify_client.now_playing()}
    except spotify_client.SpotifyError as e:
        return {"configured": True, "track": None, "error": str(e)}


@app.post("/api/spotify/{action}")
def spotify_control(action: str):
    """Walkman buttons: play / pause / next / previous (needs Premium)."""
    if action not in ("play", "pause", "next", "previous"):
        raise HTTPException(status_code=404, detail="Unknown action")
    try:
        spotify_client.control(action)
    except spotify_client.SpotifyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


# ---------- Mirror mode ----------
# How the pet reacts to a Mirror verdict, through the regular mood system: (mood, happiness boost).
MIRROR_REACTIONS = {"υψηλό": ("happy", 10), "μέτριο": ("thinking", 0), "χαμηλό": ("curious", 0), None: ("happy", 5)}


@app.get("/api/mirror/status")
def mirror_status():
    """Whether there's an outfit suggestion for today to compare a photo with."""
    suggestion = outfit_of_day.load_today()
    return {"has_suggestion": suggestion is not None, "suggestion": suggestion}


def _review_photo(data: bytes) -> dict:
    """Validate/shrink the photo, ask the vision model, then let the pet react via its mood."""
    image = mirror.prepare_image(data)
    verdict = mirror.analyze(image, pet.get_state()["name"])
    mood, boost = MIRROR_REACTIONS[verdict["match_level"]]
    return {**verdict, "pet": pet.react(mood, boost)}


@app.post("/api/mirror")
async def mirror_photo(photo: UploadFile = File(...)):
    """Compare a photo of today's outfit with the pet's suggestion (or comment freely if none).

    The photo is only held in memory for this request and never saved.
    """
    data = await photo.read(mirror.MAX_UPLOAD_BYTES + 1)  # +1 byte so oversize files are detected
    await photo.close()
    try:
        # the model call is blocking, so run it off the event loop
        return await run_in_threadpool(_review_photo, data)
    except mirror.MirrorError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ---------- Library (personal knowledge base) ----------
app.include_router(library_routes.router)

# ---------- Memory (personal facts the pet looks up on demand) ----------
app.include_router(memory_routes.router)


# Must be mounted last so it doesn't shadow the /api routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
