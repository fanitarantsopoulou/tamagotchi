"""HTTP endpoints for the library, mounted under /api/library by main.py.

Search uses POST so the query text travels in the body and never shows up in access logs.
Note contents are never logged.
"""

from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from library import importer, store

router = APIRouter(prefix="/api/library", tags=["library"])


def _http(error: store.LibraryError) -> HTTPException:
    """Map library errors to HTTP status codes."""
    status = {store.NotFound: 404, store.Conflict: 409}.get(type(error), 400)
    return HTTPException(status_code=status, detail=str(error))


def _run(fn, *args, **kwargs):
    """Call a store function, turning its user-facing errors into HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except store.LibraryError as e:
        raise _http(e)


# ---------- request bodies ----------
class BookIn(BaseModel):
    title: str = Field(max_length=store.MAX_TITLE)
    color: Optional[int] = None
    private: bool = False


class BookPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=store.MAX_TITLE)
    color: Optional[int] = None
    private: Optional[bool] = None


class ChapterIn(BaseModel):
    title: str = Field(max_length=store.MAX_TITLE)
    private: bool = False


class ChapterPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=store.MAX_TITLE)
    private: Optional[bool] = None


class NoteIn(BaseModel):
    title: str = Field(max_length=store.MAX_TITLE)
    body: str = Field("", max_length=store.MAX_BODY)
    tags: List[str] = []


class NotePatch(BaseModel):
    title: Optional[str] = Field(None, max_length=store.MAX_TITLE)
    body: Optional[str] = Field(None, max_length=store.MAX_BODY)
    tags: Optional[List[str]] = None
    chapter_id: Optional[int] = None  # move the note to another chapter (of any book)


class SaveIn(NoteIn):
    book: str = Field(max_length=store.MAX_TITLE)
    chapter: str = Field(max_length=store.MAX_TITLE)


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(20, ge=1, le=50)


# ---------- shelf and books ----------
@router.get("")
def get_shelf():
    """Every book on the shelf, with chapter and note counts."""
    return {"books": store.shelf()}


@router.post("/books", status_code=201)
def create_book(body: BookIn):
    return _run(store.create_book, body.title, body.color, body.private)


@router.get("/books/{book_id}")
def get_book(book_id: int):
    """A book's chapters with note titles and previews."""
    return _run(store.get_book, book_id)


@router.patch("/books/{book_id}")
def update_book(book_id: int, body: BookPatch):
    return _run(store.update_book, book_id, body.title, body.color, body.private)


@router.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int):
    _run(store.delete_book, book_id)


@router.get("/places")
def get_places():
    """Books and their chapters (titles only), for pickers."""
    return {"books": store.places()}


# ---------- chapters ----------
@router.post("/books/{book_id}/chapters", status_code=201)
def create_chapter(book_id: int, body: ChapterIn):
    return _run(store.create_chapter, book_id, body.title, body.private)


@router.patch("/chapters/{chapter_id}")
def update_chapter(chapter_id: int, body: ChapterPatch):
    return _run(store.update_chapter, chapter_id, body.title, body.private)


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: int):
    _run(store.delete_chapter, chapter_id)


# ---------- notes ----------
@router.post("/chapters/{chapter_id}/notes", status_code=201)
def create_note(chapter_id: int, body: NoteIn):
    return _run(store.create_note, chapter_id, body.title, body.body, body.tags)


@router.post("/save", status_code=201)
def save_note(body: SaveIn):
    """Save a note by book and chapter *name*, creating them if they don't exist yet
    (used when filing an imported file)."""
    return _run(store.save_to, body.book, body.chapter, body.title, body.body, body.tags, include_private=True)


@router.get("/notes/{note_id}")
def get_note(note_id: int):
    return _run(store.get_note, note_id)


@router.patch("/notes/{note_id}")
def update_note(note_id: int, body: NotePatch):
    return _run(store.update_note, note_id, body.title, body.body, body.tags, body.chapter_id)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int):
    _run(store.delete_note, note_id)


# ---------- search and import ----------
@router.post("/search")
def search_notes(body: SearchIn):
    """The library's own search box (includes private books: it's only shown to you)."""
    return {"results": _run(store.find, body.query, body.limit, include_private=True, match_all=True)}


@router.post("/import")
async def import_file(file: UploadFile = File(...)):
    """Read an uploaded .txt / .md / .pdf and suggest where to file it. Nothing is saved yet:
    the user confirms the book and chapter, then the page creates the note."""
    data = await file.read(importer.max_bytes(file.filename) + 1)  # +1 byte so oversize files are detected
    await file.close()
    try:
        imported = await run_in_threadpool(importer.read, file.filename, data)
    except importer.FileRejected as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        suggestion = await run_in_threadpool(store.suggest_place, imported.body)
    except Exception:  # a suggestion is a nice-to-have; the import still works without one
        suggestion = None
    return {"title": imported.title, "body": imported.body, "kind": imported.kind, "suggestion": suggestion}
