"""HTTP endpoints for the reading shelf, mounted under /api/reading by main.py."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from reading import store

router = APIRouter(prefix="/api/reading", tags=["reading"])


class BookIn(BaseModel):
    title: str = Field(max_length=store.MAX_TITLE)
    author: str = Field("", max_length=store.MAX_AUTHOR)
    status: str = "read"
    rating: int = 0
    color: str = ""  # "#rrggbb", or "" for the automatic cover color


class BookPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=store.MAX_TITLE)
    author: Optional[str] = Field(None, max_length=store.MAX_AUTHOR)
    status: Optional[str] = None
    rating: Optional[int] = None
    color: Optional[str] = None


def _run(fn, *args, **kwargs):
    """Call a store function, turning its user-facing errors into HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except store.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except store.ReadingError as e:
        raise HTTPException(status_code=400, detail=str(e))


class FillIn(BaseModel):
    count: int = Field(ge=0, le=store.MAX_BOOKS)


@router.get("")
def list_books():
    """The books, bottom of the pile first, and whether the shelf was already filled with blanks."""
    return store.shelf()


@router.post("/fill")
def fill_shelf(body: FillIn):
    """Fill a new shelf with blank books (only the first time)."""
    return store.fill(body.count)


@router.post("", status_code=201)
def add_book(body: BookIn):
    return _run(store.add, body.title, body.author, body.status, body.rating, body.color)


@router.patch("/{book_id}")
def update_book(book_id: int, body: BookPatch):
    return _run(store.update, book_id, body.title, body.author, body.status, body.rating, body.color)


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int):
    _run(store.delete, book_id)
