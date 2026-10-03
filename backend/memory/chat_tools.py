"""How the chat uses the memory: looked up on demand, never sent as a whole.

The prompt only says which categories exist; the model calls `recall` when a message touches
something personal and gets back just the matching facts. Private facts are invisible here.
Any storage failure becomes a short tool result, so the chat carries on.
"""

import logging
import sqlite3
from typing import List, Optional

from anthropic import beta_tool

from memory import store

log = logging.getLogger("memory")

PROMPT = """
Your memory of your bestie (personal facts, looked up on demand):
- Categories: {categories}.
- Before answering anything personal (a person's name, their job, colleagues, friends, family, \
what they watch or like, "θυμάσαι...;"), call recall to check what you know. Don't guess; if \
there's nothing, say you don't know yet.
- When your bestie asks you to remember something ("θυμήσου ότι...") or clearly tells you a \
lasting personal fact (a new friend, a new job, a show they started), save it with remember: one \
short fact per call, in the third person ("Η Μαρία είναι η team leader της"), with the person or \
title as the subject. If recall shows you already know it, use update_memory instead.
- Only use forget when your bestie clearly asks you to forget that exact fact.
- Never show the #ids; they're only for the tools."""


def prompt() -> str:
    return PROMPT.format(categories=", ".join(f"{k} ({c.label})" for k, c in store.CATEGORIES.items()))


def _line(m: dict) -> str:
    subject = f"{m['subject']}: " if m["subject"] else ""
    return f"#{m['id']} [{m['category']}] {subject}{m['text']}"


def tools(changes: List[str]) -> list:
    """Memory tools for one chat reply; edits are reported in `changes`."""

    @beta_tool
    def recall(query: str = "", category: Optional[str] = None) -> str:
        """Look up what you remember about your bestie.

        Args:
            query: Names or keywords, e.g. "Μαρία", "δουλειά", "Severance". Empty = the whole category.
            category: Optionally limit to one category: me, work, colleagues, friends, family, watching, likes, other.
        """
        try:
            found = store.search(query, category, include_private=False)
        except (store.MemoryStoreError, sqlite3.Error):
            log.warning("Memory recall failed")  # never log the query or the facts
            return "Memory is unavailable right now."
        return "\n".join(_line(m) for m in found) if found else "Nothing remembered about that."

    @beta_tool
    def remember(category: str, text: str, subject: str = "") -> str:
        """Save one personal fact about your bestie.

        Args:
            category: me, work, colleagues, friends, family, watching, likes or other.
            text: The fact, short, e.g. "Η Μαρία είναι η team leader της, πολύ αυστηρή με τα deadlines".
            subject: Who or what it's about, e.g. "Μαρία" or "Severance" (empty for facts about your bestie).
        """
        try:
            m = store.add(category, text, subject)
        except store.MemoryStoreError as e:
            return f"Not saved: {e}"
        except sqlite3.Error:
            log.warning("Memory save failed")
            return "Not saved: memory is unavailable right now."
        changes.append(f"remembered: {m['subject'] + ': ' if m['subject'] else ''}{m['text']}")
        return "Remembered."

    @beta_tool
    def update_memory(memory_id: int, text: Optional[str] = None, subject: Optional[str] = None,
                      category: Optional[str] = None) -> str:
        """Correct or extend a fact you already remember. Only pass what changes.

        Args:
            memory_id: The N in #N from recall.
            text: The new text of the fact.
            subject: The new subject.
            category: The new category.
        """
        try:
            m = store.update(memory_id, category, text, subject, include_private=False)
        except store.MemoryStoreError as e:
            return f"Not updated: {e}"
        except sqlite3.Error:
            return "Not updated: memory is unavailable right now."
        changes.append(f"updated memory: {m['subject'] + ': ' if m['subject'] else ''}{m['text']}")
        return "Updated."

    @beta_tool
    def forget(memory_id: int) -> str:
        """Delete a fact, only when your bestie clearly asked you to forget it.

        Args:
            memory_id: The N in #N from recall.
        """
        try:
            m = store.remove(memory_id, include_private=False)
        except store.MemoryStoreError as e:
            return f"Not deleted: {e}"
        except sqlite3.Error:
            return "Not deleted: memory is unavailable right now."
        changes.append(f"forgot: {m['subject'] + ': ' if m['subject'] else ''}{m['text']}")
        return "Forgotten."

    return [recall, remember, update_memory, forget]
