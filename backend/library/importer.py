"""Turn an uploaded file into note text: .txt, .md and (text-based) .pdf.

Files are checked by extension, size and content, read in memory and never written to disk.
Nothing here talks to the network.
"""

import io
import re
from dataclasses import dataclass
from pathlib import PurePath

MAX_TEXT_BYTES = 2 * 1024 * 1024  # .txt / .md
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 200
TEXT_TYPES = {".txt", ".md", ".markdown"}
PDF_TYPES = {".pdf"}
ACCEPTED = sorted(TEXT_TYPES | PDF_TYPES)


class FileRejected(Exception):
    """The file can't be imported; the message is safe to show to the user."""


@dataclass
class Imported:
    title: str
    body: str
    kind: str  # "text", "markdown" or "pdf"


def max_bytes(filename: str) -> int:
    """Size limit for a file, by its extension (callers read at most this + 1 bytes)."""
    return MAX_PDF_BYTES if PurePath(filename or "").suffix.lower() in PDF_TYPES else MAX_TEXT_BYTES


def read(filename: str, data: bytes) -> Imported:
    """Validate and extract the text of an uploaded file."""
    name = PurePath(filename or "untitled").name
    suffix = PurePath(name).suffix.lower()
    if suffix not in TEXT_TYPES | PDF_TYPES:
        raise FileRejected(f"Only {', '.join(ACCEPTED)} files can be added.")
    if len(data) > max_bytes(name):
        raise FileRejected(f"That file is too big (max {max_bytes(name) // (1024 * 1024)} MB).")
    if not data.strip():
        raise FileRejected("That file is empty.")

    if suffix in PDF_TYPES:
        body, kind = _pdf_text(data), "pdf"
    else:
        body, kind = _decode(data), "markdown" if suffix != ".txt" else "text"
    return Imported(title=_title(name, body, kind), body=body.strip(), kind=kind)


def _decode(data: bytes) -> str:
    """Decode text as UTF-8, falling back to the Windows Greek code page; reject binary files."""
    if b"\x00" in data[:8192]:
        raise FileRejected("That doesn't look like a text file.")
    for encoding in ("utf-8-sig", "cp1253"):
        try:
            return data.decode(encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    raise FileRejected("Couldn't read the file's text encoding (save it as UTF-8).")


def _pdf_text(data: bytes) -> str:
    """Extract the text of a PDF, page by page. Scanned PDFs (images only) have no text to extract."""
    if not data.startswith(b"%PDF-"):
        raise FileRejected("That isn't a valid PDF file.")
    from pypdf import PdfReader  # imported lazily: only needed for PDFs
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise FileRejected("That PDF is password-protected.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise FileRejected(f"That PDF has too many pages (max {MAX_PDF_PAGES}).")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except (PdfReadError, ValueError, KeyError):
        raise FileRejected("Couldn't read that PDF.") from None
    text = "\n\n".join(p for p in pages if p)
    if not text:
        raise FileRejected("That PDF has no text in it (it may be a scan).")
    return re.sub(r"\n{3,}", "\n\n", text)


def _title(filename: str, body: str, kind: str) -> str:
    """The note title: a Markdown file's first heading, otherwise the file name."""
    if kind == "markdown":
        heading = re.search(r"^#{1,3}\s+(.+)$", body, re.MULTILINE)
        if heading:
            return heading.group(1).strip()[:120]
    stem = PurePath(filename).stem.replace("_", " ").replace("-", " ")
    return (" ".join(stem.split()) or "Imported note")[:120]
