from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class ExtractionResult:
    __slots__ = ("text", "source", "error")

    def __init__(self, text: str, source: str, error: str | None = None) -> None:
        self.text = text
        self.source = source
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# EPUB extractor  (ebooklib → lxml)
# ---------------------------------------------------------------------------

def _extract_epub(path: Path, max_chars: int) -> ExtractionResult:
    try:
        import ebooklib  # type: ignore[import-untyped]
        from ebooklib import epub
        from lxml import etree
    except ImportError as exc:
        return ExtractionResult("", "epub", error=f"missing dependency: {exc}")

    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
    except Exception as exc:
        return ExtractionResult("", "epub", error=f"epub open failed: {exc}")

    chunks: list[str] = []
    total = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        if total >= max_chars:
            break
        try:
            raw = item.get_content()
            root = etree.fromstring(raw)
            text = " ".join(root.itertext())
            text = _normalise(text)
            take = min(len(text), max_chars - total)
            chunks.append(text[:take])
            total += take
        except Exception as exc:
            logger.debug("Skipping epub item %s: %s", item.get_name(), exc)

    return ExtractionResult("\n\n".join(chunks), "epub")


# ---------------------------------------------------------------------------
# PDF extractor  (pdfminer.six)
# ---------------------------------------------------------------------------

def _extract_pdf(path: Path, max_chars: int) -> ExtractionResult:
    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-untyped]
    except ImportError as exc:
        return ExtractionResult("", "pdf", error=f"missing dependency: {exc}")

    try:
        raw = extract_text(str(path), maxpages=0)
        text = _normalise(raw)
        return ExtractionResult(text[:max_chars], "pdf")
    except Exception as exc:
        return ExtractionResult("", "pdf", error=f"pdf extraction failed: {exc}")


# ---------------------------------------------------------------------------
# OPF / metadata fallback  (uses description + comments from metadata.opf)
# ---------------------------------------------------------------------------

def _extract_opf(book_dir: Path, max_chars: int) -> ExtractionResult:
    opf_files = list(book_dir.glob("*.opf"))
    if not opf_files:
        return ExtractionResult("", "opf", error="no .opf file found")

    try:
        from lxml import etree
    except ImportError as exc:
        return ExtractionResult("", "opf", error=f"missing dependency: {exc}")

    try:
        tree = etree.parse(str(opf_files[0]))
        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "opf": "http://www.idpf.org/2007/opf",
        }
        parts: list[str] = []
        for tag in ("dc:title", "dc:creator", "dc:description", "dc:subject"):
            for el in tree.findall(f".//{tag}", ns):
                if el.text:
                    parts.append(el.text.strip())

        text = _normalise(" ".join(parts))
        return ExtractionResult(text[:max_chars], "opf")
    except Exception as exc:
        return ExtractionResult("", "opf", error=f"opf parse failed: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(
    library_root: Path,
    relative_path: str,
    fmt: str,
    max_chars: int,
) -> ExtractionResult:
    """Extract readable text from a book file.

    Tries the given format first, then falls back to OPF metadata from the
    book's directory so we always return *something* indexable.

    Args:
        library_root: Absolute path to the Calibre library root.
        relative_path: Path relative to library_root (e.g. "Author/Book/book.epub").
        fmt: Format string from Calibre (e.g. "EPUB", "PDF").
        max_chars: Hard cap on returned text length.
    """
    full_path = library_root / relative_path
    book_dir = full_path.parent

    result: ExtractionResult
    fmt_upper = fmt.upper()

    if fmt_upper == "EPUB":
        result = _extract_epub(full_path, max_chars)
    elif fmt_upper == "PDF":
        result = _extract_pdf(full_path, max_chars)
    else:
        result = ExtractionResult("", fmt_upper, error=f"unsupported format: {fmt_upper}")

    if result.ok and result.text.strip():
        return result

    # Fallback: OPF metadata gives at least title/author/description
    opf_result = _extract_opf(book_dir, max_chars)
    if opf_result.ok and opf_result.text.strip():
        if not result.ok:
            logger.info(
                "Format extraction failed for %s (%s), using OPF fallback: %s",
                relative_path, fmt, result.error,
            )
        return opf_result

    # Return whatever we have, even if empty
    return result if result.ok else opf_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()
