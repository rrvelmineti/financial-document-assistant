"""Read uploaded files page by page and split them into passages that never cross a page."""
import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

CHUNK_CHARS = 1_000
OVERLAP_CHARS = 200


class DocumentError(ValueError):
    """The file could not be read as a document. The message is safe to show the user."""


@dataclass
class Page:
    number: int      # 1-based, as printed by a PDF viewer
    text: str


@dataclass
class Chunk:
    page: int
    ordinal: int     # position within the document
    text: str
    context: str = ""   # units or year columns stated elsewhere on the page; shown to the model, not embedded


def clean(text):
    text = text.replace(" ", " ").replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def read_pages(filename, data, max_pages):
    name = filename.lower()
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise DocumentError("This file is not a valid PDF.")
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise DocumentError("Password-protected PDFs are not supported.")
            if len(reader.pages) > max_pages:
                raise DocumentError(f"The PDF has {len(reader.pages)} pages; the limit is {max_pages}.")
            pages = [Page(i, clean(p.extract_text() or "")) for i, p in enumerate(reader.pages, 1)]
        except DocumentError:
            raise
        except (PdfReadError, ValueError, KeyError, TypeError, OSError):
            raise DocumentError("The PDF could not be read. It may be damaged.") from None
    elif name.endswith((".txt", ".md")):
        try:
            pages = [Page(1, clean(data.decode("utf-8")))]
        except UnicodeDecodeError:
            raise DocumentError("Text files must be UTF-8.") from None
    else:
        raise DocumentError("Upload a PDF, .txt or .md file.")
    if not any(p.text for p in pages):
        raise DocumentError("No text could be found. Scanned PDFs need OCR before upload.")
    return pages


UNITS = re.compile(r"\((?:dollars|amounts|in)[^()\n]{0,40}(?:thousands|millions|billions)[^()\n]{0,20}\)", re.I)
YEAR_COLUMNS = re.compile(r"^(?:FY ?)?(?:19|20)\d\d(?:\s+(?:FY ?)?(?:19|20)\d\d)+$", re.M)


def page_context(text):
    """Units and year columns stated once on a page, e.g. '(Dollars in Thousands)' and '2024 2023'.

    In financial statement PDFs these often land at the top or bottom of the extracted page, far from
    the figures, so a passage can lose them. They are repeated at the start of each passage.
    """
    parts = []
    if m := UNITS.search(text):
        parts.append(m.group(0))
    if m := YEAR_COLUMNS.search(text):
        parts.append("columns: " + " ".join(m.group(0).split()))
    return "; ".join(parts)


def chunk_pages(pages, size=CHUNK_CHARS, overlap=OVERLAP_CHARS):
    """Split each page on line breaks into passages of about `size` characters, with overlap."""
    chunks = []
    for page in pages:
        if not page.text:
            continue
        context = page_context(page.text)
        first = len(chunks)
        lines = [ln for ln in page.text.split("\n") if ln.strip()]
        current = ""
        for line in lines:
            while len(line) > size:                       # very long line: split on a space
                cut = line.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                if current:
                    chunks.append(Chunk(page.number, len(chunks), current))
                    current = current[-overlap:]
                current = (current + "\n" + line[:cut]).strip()
                line = line[cut:].strip()
            if current and len(current) + len(line) + 1 > size:
                chunks.append(Chunk(page.number, len(chunks), current))
                tail = current[-overlap:]
                current = tail[tail.find(" ") + 1:] if " " in tail else tail
            current = (current + "\n" + line).strip() if current else line
        if current:
            chunks.append(Chunk(page.number, len(chunks), current))
        if context:
            for c in chunks[first:]:
                missing = [p for p in context.split("; ") if p.removeprefix("columns: ") not in c.text]
                c.context = "; ".join(missing)
    return chunks
