"""The personal reading shelf: books you've read or are reading, with a 1-5 rating.

A small JSON file (data/reading.json), written atomically like the closet:
{"filled": bool, "books": [...]}. The first time the shelf is shown it is filled with blank
(untitled) books so it looks full; those are kept until you title or delete them.
"""

import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import storage

READING_FILE = Path(__file__).resolve().parent.parent / "data" / "reading.json"
LOCK = threading.RLock()  # one load-change-save at a time
STATUSES = ("read", "reading", "shelf")  # shelf = sitting on the shelf, not started yet
MAX_TITLE = 120
MAX_AUTHOR = 80
MAX_BOOKS = 200
MAX_RATING = 5
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")  # a cover color, or "" for the automatic one


class NotFound(LookupError):
    pass


class ReadingError(ValueError):
    """An edit that can't be applied; shown to the user."""


def _load() -> Dict[str, Any]:
    data = json.loads(READING_FILE.read_text()) if READING_FILE.exists() else {}
    if isinstance(data, list):  # the first version stored just the list of books
        data = {"filled": False, "books": data}
    return {"filled": data.get("filled", False), "books": data.get("books", [])}


def _save(data: Dict[str, Any]) -> None:
    storage.write_json(READING_FILE, data)


def shelf() -> Dict[str, Any]:
    with LOCK:
        return _load()


def fill(count: int) -> Dict[str, Any]:
    """Add `count` blank books, once: later calls do nothing, so deleted blanks stay deleted."""
    with LOCK:
        data = _load()
        if not data["filled"]:
            books = data["books"]
            next_id = max((b["id"] for b in books), default=0) + 1
            room = max(0, min(count, MAX_BOOKS - len(books)))
            # blanks go under the existing books: the newest book stays on top of the pile
            blanks = [{"id": next_id + i, "title": "", "author": "", "status": "read", "rating": 0} for i in range(room)]
            data["books"] = blanks + books
            data["filled"] = True
            _save(data)
        return data


def _clean(title: Optional[str], author: Optional[str], status: Optional[str], rating: Optional[int],
           color: Optional[str] = None) -> Dict[str, Any]:
    """Validate the given fields (None = not given) and return just those, trimmed."""
    out: Dict[str, Any] = {}
    if title is not None:  # may be empty: a blank book on the shelf
        out["title"] = title.strip()[:MAX_TITLE]
    if author is not None:
        out["author"] = author.strip()[:MAX_AUTHOR]
    if status is not None:
        if status not in STATUSES:
            raise ReadingError(f"Status must be one of: {', '.join(STATUSES)}.")
        out["status"] = status
    if rating is not None:
        if not 0 <= rating <= MAX_RATING:
            raise ReadingError(f"Rating must be 0-{MAX_RATING} (0 = not rated yet).")
        out["rating"] = rating
    if color is not None:
        if color and not COLOR_RE.match(color):
            raise ReadingError("Color must look like #a1b2c3.")
        out["color"] = color.lower()
    return out


def add(title: str, author: str = "", status: str = "read", rating: int = 0, color: str = "") -> Dict[str, Any]:
    fields = _clean(title, author, status, rating, color)
    if not fields["title"]:
        raise ReadingError("A book needs a title.")
    with LOCK:
        data = _load()
        books = data["books"]
        if len(books) >= MAX_BOOKS:
            raise ReadingError(f"The shelf is full ({MAX_BOOKS} books).")
        book = {"id": max((b["id"] for b in books), default=0) + 1, **fields}
        books.append(book)
        _save(data)
        return book


def update(book_id: int, title=None, author=None, status=None, rating=None, color=None) -> Dict[str, Any]:
    fields = _clean(title, author, status, rating, color)
    with LOCK:
        data = _load()
        for book in data["books"]:
            if book["id"] == book_id:
                book.update(fields)
                _save(data)
                return book
    raise NotFound(f"No book #{book_id}.")


def delete(book_id: int) -> None:
    with LOCK:
        data = _load()
        kept = [b for b in data["books"] if b["id"] != book_id]
        if len(kept) == len(data["books"]):
            raise NotFound(f"No book #{book_id}.")
        data["books"] = kept
        _save(data)
