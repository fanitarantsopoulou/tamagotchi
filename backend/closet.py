"""Makeup bag & closet storage: a small JSON file the pet can read and edit."""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import storage

CLOSET_FILE = Path(__file__).resolve().parent / "data" / "closet.json"
LOCK = threading.RLock()  # one load-change-save at a time (re-entrant: load() may save)
CATEGORIES = ("makeup", "clothes")
# Fields each category may hold; anything else is ignored.
FIELDS = {
    "makeup": ("type", "brand", "product", "shade", "notes"),
    "clothes": ("type", "item", "brand", "color", "notes"),
}


class ClosetError(ValueError):
    """An edit that can't be applied (unknown id, bad category...); shown to the model."""


def load() -> Dict[str, List[Dict[str, Any]]]:
    """Read the closet, giving every item a stable numeric id if it doesn't have one yet."""
    with LOCK:
        data = json.loads(CLOSET_FILE.read_text()) if CLOSET_FILE.exists() else {}
        closet = {cat: data.get(cat, []) for cat in CATEGORIES}
        next_id = max((i.get("id", 0) for cat in CATEGORIES for i in closet[cat]), default=0) + 1
        changed = False
        for cat in CATEGORIES:
            for item in closet[cat]:
                if "id" not in item:
                    item["id"] = next_id
                    next_id += 1
                    changed = True
        if changed:
            save(closet)
        return closet


def save(closet: Dict[str, List[Dict[str, Any]]]) -> None:
    """Write the closet to disk atomically via a temp file."""
    storage.write_json(CLOSET_FILE, closet)


def describe(item: Dict[str, Any], category: str) -> str:
    """One readable line for an item, e.g. '#3 NYX Soft Matte Lip Cream, shade Rome'."""
    if category == "makeup":
        text = f"{item.get('brand', '')} {item.get('product', '')}".strip()
        if item.get("shade"):
            text += f", shade {item['shade']}"
    else:
        text = item.get("item", "")
        if item.get("brand"):
            text = f"{item['brand']} {text}"
        if item.get("color"):
            text += f" ({item['color']})"
    if item.get("notes"):
        text += f" - {item['notes']}"
    return f"#{item['id']} [{item.get('type', category)}] {text}"


def as_text() -> str:
    """The whole closet as prompt-ready lines, grouped by category."""
    closet = load()
    lines = []
    for cat in CATEGORIES:
        lines.append(f"{cat.capitalize()}:")
        lines += [f"  {describe(item, cat)}" for item in closet[cat]] or ["  (empty)"]
    return "\n".join(lines)


def _clean(category: str, fields: Dict[str, Optional[str]]) -> Dict[str, str]:
    """Keep only allowed, non-empty fields for the category."""
    if category not in CATEGORIES:
        raise ClosetError(f"category must be one of {CATEGORIES}")
    return {k: str(v).strip() for k, v in fields.items() if k in FIELDS[category] and v and str(v).strip()}


def _find(closet: Dict[str, List[Dict[str, Any]]], item_id: int):
    """Return (category, item) for an id, or raise if it doesn't exist."""
    for cat in CATEGORIES:
        for item in closet[cat]:
            if item["id"] == item_id:
                return cat, item
    raise ClosetError(f"No item with id #{item_id}.")


def add(category: str, fields: Dict[str, Optional[str]]) -> str:
    """Add a new item and return a description of it."""
    with LOCK:
        item = _clean(category, fields)
        if not item.get("type") or not (item.get("product") or item.get("item")):
            raise ClosetError("An item needs at least a type and a product/item name.")
        closet = load()
        item["id"] = max((i["id"] for cat in CATEGORIES for i in closet[cat]), default=0) + 1
        closet[category].append(item)
        save(closet)
        return describe(item, category)


def update(item_id: int, fields: Dict[str, Optional[str]]) -> str:
    """Change some fields of an existing item and return its new description."""
    with LOCK:
        closet = load()
        category, item = _find(closet, item_id)
        changes = _clean(category, fields)
        if not changes:
            raise ClosetError("Nothing to update.")
        item.update(changes)
        save(closet)
        return describe(item, category)


def remove(item_id: int) -> str:
    """Delete an item and return a description of what was removed."""
    with LOCK:
        closet = load()
        category, item = _find(closet, item_id)
        closet[category].remove(item)
        save(closet)
        return describe(item, category)
