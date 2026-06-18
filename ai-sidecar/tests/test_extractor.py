from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from sidecar.ingestion.extractor import ExtractionResult, extract_text, _normalise


# ---------------------------------------------------------------------------
# Unit tests — pure helpers
# ---------------------------------------------------------------------------

class TestNormalise:
    def test_collapses_whitespace(self):
        assert _normalise("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert _normalise("  hi  ") == "hi"

    def test_newlines_become_spaces(self):
        assert _normalise("line1\nline2") == "line1 line2"

    def test_empty_string(self):
        assert _normalise("") == ""


class TestExtractionResult:
    def test_ok_when_no_error(self):
        r = ExtractionResult("text", "epub")
        assert r.ok is True

    def test_not_ok_when_error(self):
        r = ExtractionResult("", "epub", error="something went wrong")
        assert r.ok is False


# ---------------------------------------------------------------------------
# Integration tests — real file I/O with synthetic files
# ---------------------------------------------------------------------------

def _make_epub(path: Path, body_text: str) -> None:
    """Create a minimal valid EPUB at path with the given body text."""
    content_opf = """\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
    <dc:creator>Test Author</dc:creator>
    <dc:identifier id="uid">test-uid-001</dc:identifier>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter1"/>
  </spine>
</package>"""

    chapter_xhtml = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter 1</title></head>
  <body><p>{body_text}</p></body>
</html>"""

    toc_ncx = """\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="test-uid-001"/></head>
  <docTitle><text>Test Book</text></docTitle>
  <navMap/>
</ncx>"""

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", """\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/chapter1.xhtml", chapter_xhtml)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)


def _make_opf(book_dir: Path, title: str, description: str) -> None:
    opf = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>Test Author</dc:creator>
    <dc:description>{description}</dc:description>
  </metadata>
</package>"""
    (book_dir / "metadata.opf").write_text(opf)


class TestExtractEpub:
    @pytest.fixture(autouse=True)
    def require_ebooklib(self):
        pytest.importorskip("ebooklib")

    def test_extracts_body_text(self, tmp_path):
        book_dir = tmp_path / "Author" / "Test Book"
        book_dir.mkdir(parents=True)
        epub_path = book_dir / "test-book.epub"
        _make_epub(epub_path, "The quick brown fox jumps over the lazy dog.")

        result = extract_text(tmp_path, "Author/Test Book/test-book.epub", "EPUB", 10000)
        assert result.ok
        assert "quick brown fox" in result.text

    def test_source_is_epub(self, tmp_path):
        book_dir = tmp_path / "Author" / "Book"
        book_dir.mkdir(parents=True)
        epub_path = book_dir / "book.epub"
        _make_epub(epub_path, "Some content here.")
        result = extract_text(tmp_path, "Author/Book/book.epub", "EPUB", 10000)
        assert result.source == "epub"

    def test_max_chars_respected(self, tmp_path):
        book_dir = tmp_path / "Author" / "Book"
        book_dir.mkdir(parents=True)
        epub_path = book_dir / "book.epub"
        long_text = "word " * 5000
        _make_epub(epub_path, long_text)
        result = extract_text(tmp_path, "Author/Book/book.epub", "EPUB", 100)
        assert len(result.text) <= 100

    def test_falls_back_to_opf_on_bad_epub(self, tmp_path):
        book_dir = tmp_path / "Author" / "Book"
        book_dir.mkdir(parents=True)
        bad_epub = book_dir / "book.epub"
        bad_epub.write_bytes(b"not an epub")
        _make_opf(book_dir, "Fallback Title", "A fascinating description.")
        result = extract_text(tmp_path, "Author/Book/book.epub", "EPUB", 10000)
        # OPF fallback should provide the description
        assert "fascinating description" in result.text or "Fallback Title" in result.text


class TestExtractOpfFallback:
    def test_opf_fallback_returns_title_and_description(self, tmp_path):
        book_dir = tmp_path / "Author" / "Book"
        book_dir.mkdir(parents=True)
        _make_opf(book_dir, "My Great Novel", "A story about adventure.")
        result = extract_text(tmp_path, "Author/Book/book.mobi", "MOBI", 10000)
        assert "My Great Novel" in result.text or "adventure" in result.text

    def test_opf_source_label(self, tmp_path):
        book_dir = tmp_path / "Author" / "Book"
        book_dir.mkdir(parents=True)
        _make_opf(book_dir, "Title", "Description.")
        result = extract_text(tmp_path, "Author/Book/book.mobi", "MOBI", 10000)
        assert result.source == "opf"

    def test_missing_file_and_no_opf_returns_error_result(self, tmp_path):
        book_dir = tmp_path / "Author" / "Book"
        book_dir.mkdir(parents=True)
        result = extract_text(tmp_path, "Author/Book/missing.epub", "EPUB", 10000)
        assert not result.ok or result.text == ""
