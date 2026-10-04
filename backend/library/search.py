"""Search over the library's notes, behind a small interface.

The rest of the code only talks to SearchBackend (through backend()), so the full-text search
below can later be replaced by a vector store / RAG backend by writing another subclass and
returning it from backend(). The store tells the backend whenever a note is saved or deleted,
which is also exactly when a vector backend would (re)compute embeddings.

Contract for every backend: with include_private=False, it must never return notes that sit in
a private book or a private chapter.
"""

import re
import sqlite3
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List

MAX_QUERY_TERMS = 12


@dataclass
class Document:
    """What gets indexed for one note."""

    note_id: int
    title: str
    body: str
    tags: List[str]
    place: str  # "<book title> <chapter title>", so searching a topic name finds its notes


@dataclass
class Hit:
    note_id: int
    score: float  # higher = more relevant


def normalize(text: str) -> str:
    """Lowercase and strip accents, so "Σημειώσεις", "σημειωσεις" and "ΣΗΜΕΙΏΣΕΙΣ" all match."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def terms(query: str) -> List[str]:
    """The searchable words of a query, normalized."""
    return re.findall(r"\w+", normalize(query))[:MAX_QUERY_TERMS]


class SearchBackend(ABC):
    """Interface every search implementation provides."""

    @abstractmethod
    def setup(self, conn: sqlite3.Connection) -> None:
        """Create whatever storage the backend needs (called once when the database opens)."""

    @abstractmethod
    def index(self, conn: sqlite3.Connection, doc: Document) -> None:
        """Add a note, or replace it if it's already indexed."""

    @abstractmethod
    def remove(self, conn: sqlite3.Connection, note_ids: Iterable[int]) -> None:
        """Forget deleted notes."""

    @abstractmethod
    def search(self, conn: sqlite3.Connection, query: str, limit: int, include_private: bool, match_all: bool) -> List[Hit]:
        """Best matching notes, most relevant first.

        match_all=True requires every word (the search box); False ranks notes matching any word
        (the chat, where the model's query is a handful of keywords).
        """


class Fts5Search(SearchBackend):
    """SQLite FTS5 full-text search with prefix matching on normalized text.

    Each word becomes a prefix query ("pyth" finds "Python", "σημειωσ" finds "σημειώσεις"), which
    also covers most Greek word endings. Results are ranked with BM25, weighting a match in the
    title highest, then tags, then the book/chapter name, then the body.
    """

    WEIGHTS = (10.0, 1.0, 5.0, 3.0)  # title, body, tags, place (column order in the table)

    def setup(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts "
            "USING fts5(title, body, tags, place, tokenize = 'unicode61')"
        )

    def index(self, conn: sqlite3.Connection, doc: Document) -> None:
        self.remove(conn, [doc.note_id])
        conn.execute(
            "INSERT INTO notes_fts (rowid, title, body, tags, place) VALUES (?, ?, ?, ?, ?)",
            (doc.note_id, normalize(doc.title), normalize(doc.body), normalize(" ".join(doc.tags)), normalize(doc.place)),
        )

    def remove(self, conn: sqlite3.Connection, note_ids: Iterable[int]) -> None:
        conn.executemany("DELETE FROM notes_fts WHERE rowid = ?", [(i,) for i in note_ids])

    def search(self, conn: sqlite3.Connection, query: str, limit: int, include_private: bool, match_all: bool) -> List[Hit]:
        words = terms(query)
        if not words:
            return []
        # Quoting each word keeps FTS5 operators (AND, NEAR, "-"...) in user input from being parsed.
        match = (" AND " if match_all else " OR ").join(f'"{w}"*' for w in words)
        rows = conn.execute(
            f"""
            SELECT notes_fts.rowid AS note_id, bm25(notes_fts, {", ".join(map(str, self.WEIGHTS))}) AS rank
            FROM notes_fts
            JOIN notes n    ON n.id = notes_fts.rowid
            JOIN chapters c ON c.id = n.chapter_id
            JOIN books b    ON b.id = c.book_id
            WHERE notes_fts MATCH ? AND (? OR (b.private = 0 AND c.private = 0))
            ORDER BY rank
            LIMIT ?
            """,
            (match, include_private, limit),
        ).fetchall()
        return [Hit(note_id=r["note_id"], score=-r["rank"]) for r in rows]  # bm25: lower is better


_BACKEND: SearchBackend = Fts5Search()


def backend() -> SearchBackend:
    """The search implementation in use. Swap it here (e.g. for a vector store)."""
    return _BACKEND
