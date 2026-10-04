"""SQLite connection and schema for the library.

The database file lives in backend/data/, which docker-compose mounts as a volume, so notes
survive restarts and rebuilds. It is git-ignored.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_FILE = Path(os.environ.get("LIBRARY_DB", Path(__file__).resolve().parent.parent / "data" / "library.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    title_key   TEXT NOT NULL UNIQUE,            -- normalized title: no duplicates in any case/accents
    color       INTEGER NOT NULL DEFAULT 0,      -- index into the shelf palette (CSS --book-N)
    private     INTEGER NOT NULL DEFAULT 0,      -- 1 = hidden from the chat
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapters (
    id          INTEGER PRIMARY KEY,
    book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    title_key   TEXT NOT NULL,
    private     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (book_id, title_key)
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY,
    chapter_id  INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',        -- Markdown
    tags        TEXT NOT NULL DEFAULT '[]',      -- JSON list of strings
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS chapters_by_book ON chapters(book_id);
CREATE INDEX IF NOT EXISTS notes_by_chapter ON notes(chapter_id);
"""

_init_lock = threading.Lock()
_initialized = False


def _initialize(conn: sqlite3.Connection) -> None:
    """Create the tables (and the search index) the first time the database is opened."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        from library import search  # local import: search depends on this module

        conn.executescript(SCHEMA)
        search.backend().setup(conn)
        conn.commit()
        _initialized = True


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection for one unit of work: committed on success, rolled back on any error.

    A new connection per call keeps things simple and thread-safe (FastAPI runs sync endpoints in
    a thread pool); SQLite's own file locking serializes the writers.
    """
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        _initialize(conn)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
