"""Access to the Notion pages shared with the pet's integration: read, and append to the end of a page."""

import os
from typing import Any, Dict, List

from notion_client import APIResponseError, Client

MAX_PAGE_CHARS = 6000  # cap on page text sent to the model
MAX_TEXT_CHARS = 2000  # Notion's limit for one rich-text item
BLOCK_KINDS = {"paragraph", "bulleted_list_item", "numbered_list_item", "to_do", "heading_3"}


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


def _block(kind: str, text: str) -> Dict[str, Any]:
    """Build one Notion block object of the given kind holding plain text."""
    data: Dict[str, Any] = {"rich_text": [{"type": "text", "text": {"content": text[:MAX_TEXT_CHARS]}}]}
    if kind == "to_do":
        data["checked"] = False
    return {"object": "block", "type": kind, kind: data}


def append_to_page(page_id: str, text: str, kind: str = "paragraph") -> str:
    """Append text to the end of a page, one block per line. Never edits or deletes existing content."""
    if kind not in BLOCK_KINDS:
        raise ValueError(f"kind must be one of {sorted(BLOCK_KINDS)}")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Nothing to add.")
    client = _client()
    try:
        title = _title(client.pages.retrieve(page_id=page_id))
        client.blocks.children.append(block_id=page_id, children=[_block(kind, line) for line in lines[:100]])
    except APIResponseError as e:
        hint = " The integration needs the 'Insert content' capability." if e.code == "restricted_resource" else ""
        raise RuntimeError(f"Notion error: {e.code}.{hint}") from e
    return f'Added {len(lines[:100])} {kind.replace("_", " ")} block(s) to "{title}".'
