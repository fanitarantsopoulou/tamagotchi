from pathlib import Path
from typing import List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import chat
import pet

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Smart Tamagotchi")


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
    """Reply to the chat as the pet, aware of its current stats."""
    history = [m.model_dump() for m in body.messages]
    try:
        return chat.reply(history, pet.get_state())
    except chat.ChatError as e:
        raise HTTPException(status_code=503, detail=str(e))


# Must be mounted last so it doesn't shadow the /api routes.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
