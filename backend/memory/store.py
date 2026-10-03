"""Storage and search for the pet's memory (personal facts about the owner).

Kept in its own SQLite file, data/memory.db (on the Docker volume, git-ignored), separate from
the library: it's a different kind of data and can be wiped on its own.
"""

import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from zoneinfo import ZoneInfo

from library.search import normalize  # same accent/case folding as the library search

DB_FILE = Path(os.environ.get("MEMORY_DB", Path(__file__).resolve().parent.parent / "data" / "memory.db"))
TIMEZONE = ZoneInfo(os.environ.get("TZ", "Europe/Athens"))
MAX_TEXT = 500
MAX_SUBJECT = 80
MAX_RESULTS = 12


@dataclass(frozen=True)
class Category:
    label: str  # shown in MEMORY.EXE
    keywords: str  # indexed with every fact, so "σειρές" or "friends" finds the whole category


# A registry, like the theme presets: add a category here and it appears in the window and the tools.
CATEGORIES: Dict[str, Category] = {
    "me": Category("About me", "me myself εγώ ποια είμαι"),
    "work": Category("Work", "work job δουλειά εργασία"),
    "colleagues": Category("Colleagues", "colleagues coworkers συνάδελφοι συνάδελφος συναδέλφισσα"),
    "friends": Category("Friends", "friends φίλοι φίλες φίλη φίλος κολλητή"),
    "family": Category("Family", "family οικογένεια μαμά μπαμπάς αδερφή αδερφός"),
    "watching": Category("Shows & movies", "shows series movies σειρές σειρά ταινίες ταινία netflix"),
    "likes": Category("Likes & dislikes", "likes favorite αρέσει αγαπημένα"),
    "other": Category("Other", ""),
}

STOPWORDS = {"ποια", "ποιος", "ποιο", "ποιοι", "ειναι", "εχω", "μου", "την", "τον", "του", "της", "και",
             "what", "who", "the", "and", "are", "is", "my"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY,
    category    TEXT NOT NULL,
    subject     TEXT NOT NULL DEFAULT '',   -- who/what it's about, e.g. "Μαρία" or "Severance"
    text        TEXT NOT NULL,
    private     INTEGER NOT NULL DEFAULT 0, -- 1 = never shown to the chat
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(subject, text, category, tokenize = 'unicode61');
"""


class MemoryStoreError(Exception):
    """A problem with a short, user-safe message."""


class NotFound(MemoryStoreError):
    pass


class Invalid(MemoryStoreError):
    pass


_init_lock = threading.Lock()
_initialized = False


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """One short transaction: committed on success, rolled back on error."""
    global _initialized
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with _init_lock:
            if not _initialized:
                conn.executescript(SCHEMA)
                _initialized = True
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")


def _clean(category: str, subject: str, text: str) -> tuple:
    category = (category or "other").strip().lower()
    if category not in CATEGORIES:
        raise Invalid(f"Unknown category. Use one of: {', '.join(CATEGORIES)}.")
    subject = " ".join((subject or "").split())[:MAX_SUBJECT]
    text = " ".join((text or "").split())
    if not text:
        raise Invalid("Write what to remember.")
    if len(text) > MAX_TEXT:
        raise Invalid(f"Keep it short (max {MAX_TEXT} characters).")
    return category, subject, text


def _index(conn: sqlite3.Connection, memory_id: int, category: str, subject: str, text: str) -> None:
    conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
    conn.execute(
        "INSERT INTO memories_fts (rowid, subject, text, category) VALUES (?, ?, ?, ?)",
        (memory_id, normalize(subject), normalize(text),
         normalize(f"{category} {CATEGORIES[category].label} {CATEGORIES[category].keywords}")),
    )


def _row(r: sqlite3.Row) -> Dict[str, Any]:
    return {**dict(r), "private": bool(r["private"]), "category_label": CATEGORIES.get(r["category"], CATEGORIES["other"]).label}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def categories() -> List[Dict[str, str]]:
    return [{"key": k, "label": c.label} for k, c in CATEGORIES.items()]


def all_memories(include_private: bool = True) -> List[Dict[str, Any]]:
    """Every fact, in category order, then by subject."""
    order = {k: i for i, k in enumerate(CATEGORIES)}
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM memories WHERE ? OR private = 0", (include_private,)).fetchall()
    return sorted((_row(r) for r in rows), key=lambda m: (order.get(m["category"], 99), m["subject"].casefold(), m["id"]))


def get(memory_id: int, include_private: bool = True) -> Dict[str, Any]:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if r is None or (r["private"] and not include_private):
        raise NotFound("There's no such memory.")
    return _row(r)


def add(category: str, text: str, subject: str = "", private: bool = False) -> Dict[str, Any]:
    category, subject, text = _clean(category, subject, text)
    with _connect() as conn:
        now = _now()
        cur = conn.execute(
            "INSERT INTO memories (category, subject, text, private, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (category, subject, text, int(private), now, now),
        )
        _index(conn, cur.lastrowid, category, subject, text)
        memory_id = cur.lastrowid
    return get(memory_id)


def update(memory_id: int, category: Optional[str] = None, text: Optional[str] = None,
           subject: Optional[str] = None, private: Optional[bool] = None, include_private: bool = True) -> Dict[str, Any]:
    """Change a fact; only the given fields change."""
    current = get(memory_id, include_private)
    category, subject, text = _clean(
        category if category is not None else current["category"],
        subject if subject is not None else current["subject"],
        text if text is not None else current["text"],
    )
    with _connect() as conn:
        conn.execute(
            "UPDATE memories SET category = ?, subject = ?, text = ?, private = ?, updated_at = ? WHERE id = ?",
            (category, subject, text, int(private) if private is not None else int(current["private"]), _now(), memory_id),
        )
        _index(conn, memory_id, category, subject, text)
    return get(memory_id)


def remove(memory_id: int, include_private: bool = True) -> Dict[str, Any]:
    memory = get(memory_id, include_private)
    with _connect() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
    return memory


# ---------------------------------------------------------------------------
# Search (for the chat's recall tool)
# ---------------------------------------------------------------------------
def _stem(word: str) -> str:
    """Rough stemming for prefix search, so Greek word forms meet: "μαριας" -> "μαρι*" matches "Μαρία"."""
    return word[: max(3, len(word) - 2)] if len(word) > 4 else word


def search(query: str = "", category: Optional[str] = None, include_private: bool = False,
           limit: int = MAX_RESULTS) -> List[Dict[str, Any]]:
    """Facts matching any of the query's words (most relevant first), optionally within one category.
    With an empty query, the whole category is returned."""
    words = [w for w in re.findall(r"\w+", normalize(query)) if len(w) >= 3 and w not in STOPWORDS][:12]
    clauses, params = ["(? OR m.private = 0)"], [include_private]
    if category:
        clauses.append("m.category = ?")
        params.append(category)
    with _connect() as conn:
        if words:
            match = " OR ".join(f'"{_stem(w)}"*' for w in words)
            rows = conn.execute(
                f"""SELECT m.* FROM memories_fts JOIN memories m ON m.id = memories_fts.rowid
                    WHERE memories_fts MATCH ? AND {' AND '.join(clauses)}
                    ORDER BY bm25(memories_fts, 10.0, 3.0, 1.0) LIMIT ?""",
                (match, *params, limit),
            ).fetchall()
        elif category:
            rows = conn.execute(
                f"SELECT m.* FROM memories m WHERE {' AND '.join(clauses)} ORDER BY m.subject LIMIT ?",
                (*params, limit),
            ).fetchall()
        else:
            rows = []
    return [_row(r) for r in rows]
