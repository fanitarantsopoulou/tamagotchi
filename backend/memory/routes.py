"""HTTP endpoints for the MEMORY.EXE window, mounted under /api/memory by main.py."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from memory import store

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryIn(BaseModel):
    category: str
    text: str = Field(max_length=store.MAX_TEXT)
    subject: str = Field("", max_length=store.MAX_SUBJECT)
    private: bool = False


class MemoryPatch(BaseModel):
    category: Optional[str] = None
    text: Optional[str] = Field(None, max_length=store.MAX_TEXT)
    subject: Optional[str] = Field(None, max_length=store.MAX_SUBJECT)
    private: Optional[bool] = None


def _run(fn, *args, **kwargs):
    """Call a store function, turning its user-facing errors into HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except store.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except store.MemoryStoreError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_memories():
    """Every remembered fact (including private ones: this window is only shown to you)."""
    return {"categories": store.categories(), "memories": store.all_memories(include_private=True)}


@router.post("", status_code=201)
def add_memory(body: MemoryIn):
    return _run(store.add, body.category, body.text, body.subject, body.private)


@router.patch("/{memory_id}")
def update_memory(memory_id: int, body: MemoryPatch):
    return _run(store.update, memory_id, body.category, body.text, body.subject, body.private)


@router.delete("/{memory_id}", status_code=204)
def delete_memory(memory_id: int):
    _run(store.remove, memory_id)
