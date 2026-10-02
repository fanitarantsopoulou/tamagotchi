"""Read-only access to the Notion pages shared with the pet's integration."""

import os
from typing import Any, Dict, List

from notion_client import APIResponseError, Client

MAX_PAGE_CHARS = 6000  # cap on page text sent to the model


def is_configured() -> bool:
    """True when a Notion integration token is set in the environment."""
    return bool(os.environ.get("NOTION_TOKEN"))


def _client() -> Client:
    """Create a Notion API client from NOTION_TOKEN."""
    return Client(auth=os.environ["NOTION_TOKEN"])


def _plain(rich_text: List[Dict[str, Any]]) -> str:
    """Join a Notion rich-text array into plain text."""
    return "".join(part.get("plain_text", "") for part in rich_text or [])


def _title(obj: Dict[str, Any]) -> str:
    """Find the title of a page or data source (databases keep it in a different place)."""
    if obj.get("title"):
        return _plain(obj["title"])
    for prop in obj.get("properties", {}).values():
        if prop.get("type") == "title":
            return _plain(prop["title"])
    return "(untitled)"


def search(query: str = "", limit: int = 10) -> str:
    """List pages matching `query` (or all shared pages), most recently edited first."""
    try:
        result = _client().search(
            query=query,
            sort={"direction": "descending", "timestamp": "last_edited_time"},
            page_size=min(max(limit, 1), 25),
        )
    except APIResponseError as e:
        raise RuntimeError(f"Notion error: {e.code}") from e

    lines = []
    for obj in result.get("results", []):
        kind = "database" if obj["object"] == "data_source" else "page"
        lines.append(f"- [{kind}] {_title(obj)} (id: {obj['id']}, last edited {obj.get('last_edited_time', '?')[:16]})")
    return "\n".join(lines) or "No pages found. Pages must be shared with the integration (••• > Connections)."


def _block_line(block: Dict[str, Any]) -> str:
    """Turn one Notion block into a line of plain text."""
    kind = block["type"]
    data = block.get(kind, {})
    text = _plain(data.get("rich_text", []))
    if kind.startswith("heading"):
        return f"\n## {text}"
    if kind in ("bulleted_list_item", "numbered_list_item"):
        return f"- {text}"
    if kind == "to_do":
        return f"[{'x' if data.get('checked') else ' '}] {text}"
    if kind in ("child_page", "child_database"):
        return f"(sub-page: {data.get('title', '')}, id: {block['id']})"
    return text


def read_page(page_id: str) -> str:
    """Return a page's title and text content (first 100 blocks, capped in length)."""
    client = _client()
    try:
        page = client.pages.retrieve(page_id=page_id)
        blocks = client.blocks.children.list(block_id=page_id, page_size=100)
    except APIResponseError as e:
        raise RuntimeError(f"Notion error: {e.code}. Is the id right and the page shared with the integration?") from e

    body = "\n".join(line for line in (_block_line(b) for b in blocks.get("results", [])) if line.strip())
    text = f"# {_title(page)}\nLast edited: {page.get('last_edited_time', '?')[:16]}\n\n{body or '(empty page)'}"
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + "\n...(truncated)"
    return text
