"""Create, read, update and delete books, chapters and notes.

Every function opens its own short transaction (db.connect) and returns plain dicts, ready to be
sent as JSON. Problems the user can fix (missing item, duplicate title, bad input) raise
LibraryError subclasses with a short message that is safe to show.

Functions that serve the chat take include_private=False, which hides private books and
chapters completely: they are neither listed nor searchable nor writable from there.
"""

import json
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from library import db, search

TIMEZONE = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))

MAX_TITLE = 120
MAX_BODY = 300_000  # characters; roughly a 100-page PDF
MAX_TAGS = 10
MAX_TAG = 30
PALETTE_SIZE = 8  # number of --book-N colors defined in the CSS
EXCERPT_CHARS = 160
# Frequent words that say nothing about a text's topic (already normalized: lowercase, no accents).
STOPWORDS = set(
    "that this with from have will your what when there their they them were been into than then also "
    "just only some more very about which would could should these those other after before here "
    "ειναι αυτο αυτη αυτα αυτος οταν οπως ομως επισης ακομα μονο πολυ εχει εχουν ηταν οπου γιατι "
    "πρεπει μπορει μετα πριν κατα μεσα οποια οποιο οποιος ολοι ολες ολα".split()
)


class LibraryError(Exception):
    """A problem with a short, user-safe message."""


class NotFound(LibraryError):
    pass


class Conflict(LibraryError):
    pass


class Invalid(LibraryError):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")


def _title(value: str, what: str) -> str:
    value = " ".join((value or "").split())
    if not value:
        raise Invalid(f"The {what} needs a title.")
    if len(value) > MAX_TITLE:
        raise Invalid(f"The {what} title is too long (max {MAX_TITLE} characters).")
    return value


def _body(value: str) -> str:
    value = (value or "").replace("\r\n", "\n").strip()
    if len(value) > MAX_BODY:
        raise Invalid(f"The note is too long (max {MAX_BODY:,} characters).")
    return value


def _tags(values: Optional[Iterable[str]]) -> List[str]:
    """Clean tags: trimmed, no '#', no duplicates (case-insensitive), within the limits."""
    cleaned: List[str] = []
    for tag in values or []:
        tag = " ".join(str(tag).lstrip("#").split())[:MAX_TAG]
        if tag and tag.casefold() not in (t.casefold() for t in cleaned):
            cleaned.append(tag)
    if len(cleaned) > MAX_TAGS:
        raise Invalid(f"Too many tags (max {MAX_TAGS}).")
    return cleaned


def _color(value: Optional[int]) -> int:
    return int(value or 0) % PALETTE_SIZE


def _excerpt(body: str, words: List[str] = (), size: int = EXCERPT_CHARS) -> str:
    """A short plain-text preview of a note, centered on the first search word if there is one."""
    text = re.sub(r"```[\w+-]*", " ", body)  # code fences, with their language name
    text = re.sub(r"[#*_`>\[\]]+", "", text)  # the most common Markdown symbols
    text = " ".join(text.split())
    start = 0
    if words:
        # Normalize character by character so positions in the normalized text map back 1:1.
        folded = "".join(search.normalize(c)[:1] or " " for c in text)
        found = [i for i in (folded.find(w) for w in words) if i >= 0]
        if found:
            start = max(0, min(found) - size // 3)
    snippet = text[start:start + size]
    return ("…" if start else "") + snippet + ("…" if start + size < len(text) else "")


def _place(conn: sqlite3.Connection, chapter_id: int) -> Dict[str, Any]:
    """The chapter and book a note lives in."""
    row = conn.execute(
        """SELECT c.id AS chapter_id, c.title AS chapter, c.private AS chapter_private,
                  b.id AS book_id, b.title AS book, b.private AS book_private
           FROM chapters c JOIN books b ON b.id = c.book_id WHERE c.id = ?""",
        (chapter_id,),
    ).fetchone()
    if row is None:
        raise NotFound("That chapter doesn't exist.")
    return dict(row)


def _reindex(conn: sqlite3.Connection, where: str, params: tuple) -> None:
    """(Re)index the notes matching a WHERE clause on notes n / chapters c / books b."""
    rows = conn.execute(
        f"""SELECT n.id, n.title, n.body, n.tags, b.title AS book, c.title AS chapter
            FROM notes n JOIN chapters c ON c.id = n.chapter_id JOIN books b ON b.id = c.book_id
            WHERE {where}""",
        params,
    ).fetchall()
    for r in rows:
        search.backend().index(
            conn,
            search.Document(r["id"], r["title"], r["body"], json.loads(r["tags"]), f"{r['book']} {r['chapter']}"),
        )


def _unique(conn: sqlite3.Connection, sql: str, params: tuple, message: str):
    """Run an INSERT/UPDATE, turning a UNIQUE-constraint failure into a friendly Conflict."""
    try:
        return conn.execute(sql, params)
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise Conflict(message) from None
        raise


def _visible(row: sqlite3.Row, include_private: bool) -> bool:
    return include_private or not (row["book_private"] or row["chapter_private"])


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------
def shelf() -> List[Dict[str, Any]]:
    """All books for the shelf, with how many chapters and notes each one holds."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT b.*, COUNT(DISTINCT c.id) AS chapter_count, COUNT(n.id) AS note_count
               FROM books b
               LEFT JOIN chapters c ON c.book_id = b.id
               LEFT JOIN notes n ON n.chapter_id = c.id
               GROUP BY b.id ORDER BY b.created_at, b.id"""
        ).fetchall()
    return [{**dict(r), "private": bool(r["private"])} for r in rows]


def get_book(book_id: int) -> Dict[str, Any]:
    """A book with its chapters, and each chapter's notes as title + preview (no full text)."""
    with db.connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if book is None:
            raise NotFound("That book doesn't exist.")
        chapters = conn.execute(
            "SELECT * FROM chapters WHERE book_id = ? ORDER BY created_at, id", (book_id,)
        ).fetchall()
        notes = conn.execute(
            """SELECT n.* FROM notes n JOIN chapters c ON c.id = n.chapter_id
               WHERE c.book_id = ? ORDER BY n.updated_at DESC""",
            (book_id,),
        ).fetchall()

    by_chapter: Dict[int, List[Dict[str, Any]]] = {c["id"]: [] for c in chapters}
    for n in notes:
        by_chapter[n["chapter_id"]].append(
            {"id": n["id"], "title": n["title"], "tags": json.loads(n["tags"]), "excerpt": _excerpt(n["body"]),
             "created_at": n["created_at"], "updated_at": n["updated_at"]}
        )
    return {
        **dict(book),
        "private": bool(book["private"]),
        "chapters": [{**dict(c), "private": bool(c["private"]), "notes": by_chapter[c["id"]]} for c in chapters],
    }


def create_book(title: str, color: Optional[int] = None, private: bool = False) -> Dict[str, Any]:
    title = _title(title, "book")
    with db.connect() as conn:
        if color is None:  # give new books the next color on the shelf
            color = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        now = _now()
        cur = _unique(
            conn,
            "INSERT INTO books (title, title_key, color, private, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (title, search.normalize(title), _color(color), int(private), now, now),
            f"There's already a book called «{title}».",
        )
        book_id = cur.lastrowid
    return get_book(book_id)


def update_book(book_id: int, title: Optional[str] = None, color: Optional[int] = None,
                private: Optional[bool] = None) -> Dict[str, Any]:
    """Rename, recolor or (un)mark a book as private. Only the given fields change."""
    with db.connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if book is None:
            raise NotFound("That book doesn't exist.")
        new_title = _title(title, "book") if title is not None else book["title"]
        _unique(
            conn,
            "UPDATE books SET title = ?, title_key = ?, color = ?, private = ?, updated_at = ? WHERE id = ?",
            (new_title, search.normalize(new_title), _color(color) if color is not None else book["color"],
             int(private) if private is not None else book["private"], _now(), book_id),
            f"There's already a book called «{new_title}».",
        )
        if new_title != book["title"]:
            _reindex(conn, "b.id = ?", (book_id,))  # the book name is part of each note's index entry
    return get_book(book_id)


def delete_book(book_id: int) -> None:
    """Delete a book with all its chapters and notes."""
    with db.connect() as conn:
        note_ids = [r[0] for r in conn.execute(
            "SELECT n.id FROM notes n JOIN chapters c ON c.id = n.chapter_id WHERE c.book_id = ?", (book_id,))]
        if conn.execute("DELETE FROM books WHERE id = ?", (book_id,)).rowcount == 0:
            raise NotFound("That book doesn't exist.")
        search.backend().remove(conn, note_ids)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------
def create_chapter(book_id: int, title: str, private: bool = False) -> Dict[str, Any]:
    title = _title(title, "chapter")
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
            raise NotFound("That book doesn't exist.")
        now = _now()
        cur = _unique(
            conn,
            "INSERT INTO chapters (book_id, title, title_key, private, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (book_id, title, search.normalize(title), int(private), now, now),
            f"This book already has a chapter called «{title}».",
        )
        row = conn.execute("SELECT * FROM chapters WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "private": bool(row["private"]), "notes": []}


def update_chapter(chapter_id: int, title: Optional[str] = None, private: Optional[bool] = None) -> Dict[str, Any]:
    with db.connect() as conn:
        chapter = conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        if chapter is None:
            raise NotFound("That chapter doesn't exist.")
        new_title = _title(title, "chapter") if title is not None else chapter["title"]
        _unique(
            conn,
            "UPDATE chapters SET title = ?, title_key = ?, private = ?, updated_at = ? WHERE id = ?",
            (new_title, search.normalize(new_title), int(private) if private is not None else chapter["private"], _now(), chapter_id),
            f"This book already has a chapter called «{new_title}».",
        )
        if new_title != chapter["title"]:
            _reindex(conn, "c.id = ?", (chapter_id,))
        row = conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
    return {**dict(row), "private": bool(row["private"])}


def delete_chapter(chapter_id: int) -> None:
    """Delete a chapter with all its notes."""
    with db.connect() as conn:
        note_ids = [r[0] for r in conn.execute("SELECT id FROM notes WHERE chapter_id = ?", (chapter_id,))]
        if conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,)).rowcount == 0:
            raise NotFound("That chapter doesn't exist.")
        search.backend().remove(conn, note_ids)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
def _note_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
    place = _place(conn, row["chapter_id"])
    return {**dict(row), "tags": json.loads(row["tags"]), **place,
            "book_private": bool(place["book_private"]), "chapter_private": bool(place["chapter_private"])}


def get_note(note_id: int, include_private: bool = True) -> Dict[str, Any]:
    """A note with its full text and where it lives (book + chapter)."""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        note = _note_dict(conn, row) if row else None
    if note is None or not _visible(note, include_private):
        raise NotFound("That note doesn't exist.")
    return note


def create_note(chapter_id: int, title: str, body: str, tags: Optional[List[str]] = None,
                include_private: bool = True) -> Dict[str, Any]:
    title, body, tags = _title(title, "note"), _body(body), _tags(tags)
    with db.connect() as conn:
        if not _visible(_place(conn, chapter_id), include_private):
            raise NotFound("That chapter doesn't exist.")
        now = _now()
        cur = conn.execute(
            "INSERT INTO notes (chapter_id, title, body, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chapter_id, title, body, json.dumps(tags, ensure_ascii=False), now, now),
        )
        note_id = cur.lastrowid
        _reindex(conn, "n.id = ?", (note_id,))
    return get_note(note_id)


def update_note(note_id: int, title: Optional[str] = None, body: Optional[str] = None,
                tags: Optional[List[str]] = None, chapter_id: Optional[int] = None) -> Dict[str, Any]:
    """Edit a note, or move it to another chapter (of any book) with chapter_id."""
    with db.connect() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note is None:
            raise NotFound("That note doesn't exist.")
        if chapter_id is not None:
            _place(conn, chapter_id)  # raises NotFound if the target chapter is gone
        conn.execute(
            "UPDATE notes SET title = ?, body = ?, tags = ?, chapter_id = ?, updated_at = ? WHERE id = ?",
            (
                _title(title, "note") if title is not None else note["title"],
                _body(body) if body is not None else note["body"],
                json.dumps(_tags(tags), ensure_ascii=False) if tags is not None else note["tags"],
                chapter_id if chapter_id is not None else note["chapter_id"],
                _now(),
                note_id,
            ),
        )
        _reindex(conn, "n.id = ?", (note_id,))
    return get_note(note_id)


def delete_note(note_id: int) -> None:
    with db.connect() as conn:
        if conn.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount == 0:
            raise NotFound("That note doesn't exist.")
        search.backend().remove(conn, [note_id])


# ---------------------------------------------------------------------------
# Search and chat helpers
# ---------------------------------------------------------------------------
def find(query: str, limit: int = 20, include_private: bool = True, match_all: bool = True) -> List[Dict[str, Any]]:
    """Search notes; each result carries its book/chapter and a preview around the match."""
    words = search.terms(query)
    with db.connect() as conn:
        hits = search.backend().search(conn, query, limit, include_private, match_all)
        results = []
        for hit in hits:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (hit.note_id,)).fetchone()
            if row is None:
                continue  # index briefly ahead of a delete; skip it
            note = _note_dict(conn, row)
            if not _visible(note, include_private):
                continue  # belt and braces: the backend already filters private notes
            results.append({**note, "score": round(hit.score, 3), "excerpt": _excerpt(note["body"], words)})
    return results


def outline(include_private: bool = False) -> List[Dict[str, Any]]:
    """Book and chapter titles only (no note text), e.g. for telling the chat what topics exist."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT b.title AS book, c.title AS chapter, b.private AS book_private,
                      c.private AS chapter_private, COUNT(n.id) AS notes
               FROM books b LEFT JOIN chapters c ON c.book_id = b.id LEFT JOIN notes n ON n.chapter_id = c.id
               GROUP BY b.id, c.id ORDER BY b.created_at, b.id, c.created_at, c.id"""
        ).fetchall()
    books: Dict[str, List[str]] = {}
    for r in rows:
        if r["book_private"] and not include_private:
            continue
        chapters = books.setdefault(r["book"], [])
        if r["chapter"] and (include_private or not r["chapter_private"]):
            chapters.append(f"{r['chapter']} ({r['notes']})")
    return [{"book": b, "chapters": c} for b, c in books.items()]


def places() -> List[Dict[str, Any]]:
    """Every book with its chapters (ids and titles only), for the "move to..." and "save in..." pickers."""
    with db.connect() as conn:
        books = conn.execute("SELECT id, title, private FROM books ORDER BY created_at, id").fetchall()
        chapters = conn.execute("SELECT id, book_id, title, private FROM chapters ORDER BY created_at, id").fetchall()
    return [
        {"id": b["id"], "title": b["title"], "private": bool(b["private"]),
         "chapters": [{"id": c["id"], "title": c["title"], "private": bool(c["private"])}
                      for c in chapters if c["book_id"] == b["id"]]}
        for b in books
    ]


def save_to(book_title: str, chapter_title: str, title: str, body: str, tags: Optional[List[str]] = None,
            include_private: bool = False) -> Dict[str, Any]:
    """Save a note by book/chapter *name*, creating the book or chapter if needed (used by the chat).

    With include_private=False a private book or chapter of that name can't be written to.
    """
    book_title, chapter_title = _title(book_title, "book"), _title(chapter_title, "chapter")
    with db.connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE title_key = ?", (search.normalize(book_title),)).fetchone()
        chapter = None
        if book is not None:
            chapter = conn.execute(
                "SELECT * FROM chapters WHERE book_id = ? AND title_key = ?", (book["id"], search.normalize(chapter_title))
            ).fetchone()
        hidden = book is not None and (book["private"] or (chapter is not None and chapter["private"]))
    if hidden and not include_private:
        raise Conflict("That place in the library is private, so it can't be used from the chat.")

    created = []
    if book is None:
        book = create_book(book_title)
        created.append(f"book «{book['title']}»")
    if chapter is None:
        chapter = create_chapter(book["id"], chapter_title)
        created.append(f"chapter «{chapter['title']}»")
    note = create_note(chapter["id"], title, body, tags, include_private=include_private)
    return {**note, "created": created}


def suggest_place(text: str) -> Optional[Dict[str, Any]]:
    """Guess the best chapter for a new piece of text, locally (nothing leaves the server).

    The text's most frequent meaningful words are searched for, and the chapter whose notes match
    best wins. Returns None when the library has nothing similar yet.
    """
    counts = Counter(w for w in re.findall(r"\w{4,}", search.normalize(text[:20_000]))
                     if not w.isdigit() and w not in STOPWORDS)
    common = [w for w, _ in counts.most_common(search.MAX_QUERY_TERMS)]
    if not common:
        return None
    totals: Counter = Counter()
    places: Dict[int, Dict[str, Any]] = {}
    for hit in find(" ".join(common), limit=30, include_private=True, match_all=False):
        totals[hit["chapter_id"]] += hit["score"]
        places[hit["chapter_id"]] = hit
    if not totals:
        return None
    best = places[totals.most_common(1)[0][0]]
    return {k: best[k] for k in ("book_id", "book", "chapter_id", "chapter")}
