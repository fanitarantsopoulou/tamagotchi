from pathlib import Path
from typing import List, Literal

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import chat
import pet
import theme

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Smart Tamagotchi")


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
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


@app.get("/api/chat/greeting")
def chat_greeting():
    """Return the line the pet opens every chat with."""
    return {"message": chat.GREETING}


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


# Must be mounted last so it doesn't shadow the /api routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
