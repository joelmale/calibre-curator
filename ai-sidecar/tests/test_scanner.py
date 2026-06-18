from __future__ import annotations

import pytest

from sidecar.db.calibre_reader import CalibreBookRecord, CalibreFormatInfo
from sidecar.ingestion.scanner import (
    compute_formats_hash,
    compute_metadata_hash,
    detect_changed_books,
)


def _make_record(
    book_id: int = 1,
    title: str = "Test Book",
    authors: list[str] | None = None,
    tags: list[str] | None = None,
    formats: list[str] | None = None,
    last_modified: str | None = "2026-01-01T00:00:00",
) -> CalibreBookRecord:
    fmt_details = [
        CalibreFormatInfo(format=f, name=f"test-book", uncompressed_size=1024)
        for f in (formats or ["EPUB"])
    ]
    return CalibreBookRecord(
        book_id=book_id,
        title=title,
        sort=None,
        author_sort=None,
        path=f"Author/Test Book ({book_id})",
        timestamp=None,
        pubdate=None,
        last_modified=last_modified,
        authors=authors or ["Test Author"],
        tags=tags or [],
        format_details=fmt_details,
    )


class TestComputeMetadataHash:
    def test_same_record_produces_same_hash(self):
        r = _make_record()
        assert compute_metadata_hash(r) == compute_metadata_hash(r)

    def test_title_change_produces_different_hash(self):
        a = _make_record(title="Book A")
        b = _make_record(title="Book B")
        assert compute_metadata_hash(a) != compute_metadata_hash(b)

    def test_author_change_produces_different_hash(self):
        a = _make_record(authors=["Alice"])
        b = _make_record(authors=["Bob"])
        assert compute_metadata_hash(a) != compute_metadata_hash(b)

    def test_tag_change_produces_different_hash(self):
        a = _make_record(tags=["sci-fi"])
        b = _make_record(tags=["fantasy"])
        assert compute_metadata_hash(a) != compute_metadata_hash(b)

    def test_hash_is_hex_string(self):
        h = compute_metadata_hash(_make_record())
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestComputeFormatsHash:
    def test_same_formats_same_hash(self):
        r = _make_record(formats=["EPUB", "PDF"])
        assert compute_formats_hash(r) == compute_formats_hash(r)

    def test_added_format_produces_different_hash(self):
        a = _make_record(formats=["EPUB"])
        b = _make_record(formats=["EPUB", "PDF"])
        assert compute_formats_hash(a) != compute_formats_hash(b)

    def test_format_order_does_not_matter(self):
        # records are sorted by format name, so order should not affect hash
        a = _make_record(formats=["EPUB", "PDF"])
        b = _make_record(formats=["PDF", "EPUB"])
        assert compute_formats_hash(a) == compute_formats_hash(b)


class TestDetectChangedBooks:
    def test_all_new_books_are_changed(self):
        records = [_make_record(book_id=1), _make_record(book_id=2)]
        changed, removed = detect_changed_books(records, known={})
        assert len(changed) == 2
        assert removed == set()

    def test_unchanged_book_is_not_in_changed(self):
        record = _make_record(book_id=1)
        meta_h = compute_metadata_hash(record)
        fmt_h = compute_formats_hash(record)
        changed, removed = detect_changed_books([record], known={1: (meta_h, fmt_h)})
        assert changed == []
        assert removed == set()

    def test_modified_title_marks_book_changed(self):
        old = _make_record(book_id=1, title="Old Title")
        new = _make_record(book_id=1, title="New Title")
        meta_h = compute_metadata_hash(old)
        fmt_h = compute_formats_hash(old)
        changed, _ = detect_changed_books([new], known={1: (meta_h, fmt_h)})
        assert len(changed) == 1
        assert changed[0].book_id == 1

    def test_removed_book_in_removed_ids(self):
        record = _make_record(book_id=1)
        meta_h = compute_metadata_hash(record)
        fmt_h = compute_formats_hash(record)
        # book 1 was known but is no longer in Calibre
        changed, removed = detect_changed_books([], known={1: (meta_h, fmt_h)})
        assert changed == []
        assert removed == {1}

    def test_mixed_scenario(self):
        existing = _make_record(book_id=1)
        meta_h = compute_metadata_hash(existing)
        fmt_h = compute_formats_hash(existing)

        new_book = _make_record(book_id=2)
        changed_book = _make_record(book_id=1, title="Updated Title")

        known = {
            1: (meta_h, fmt_h),   # will change
            99: ("old", "old"),   # will be removed
        }
        changed, removed = detect_changed_books([new_book, changed_book], known=known)
        assert {r.book_id for r in changed} == {1, 2}
        assert removed == {99}
