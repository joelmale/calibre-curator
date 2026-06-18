"""Unit tests for BookAiRepository.get_incomplete_book_ids.

Verifies that the fix for the stuck-indexing bug works correctly:
- 'pending' books ARE returned (they were previously excluded)
- 'indexed' books are NOT returned
- intermediate statuses ('failed', 'extracting', 'chunked') are returned
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from sidecar.db.repositories import BookAiRepository
from sidecar.db.schema import init_db


@pytest.fixture()
def mem_db():
    """In-memory SQLite with the sidecar schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # init_db expects a path; use the connection directly by applying the schema
    import importlib.resources as ir
    from pathlib import Path
    schema_path = Path(__file__).parent.parent / "sidecar" / "db" / "schema.py"
    # Call init_db with a temp path, but we want to re-use our in-memory conn.
    # Instead, apply the DDL directly from the schema module.
    from sidecar.db import schema as schema_mod
    import inspect, re
    # Extract CREATE TABLE statements from init_db source
    src = inspect.getsource(schema_mod.init_db)
    # Run them on our in-memory connection
    # Simpler: just call the actual function with ":memory:" — SQLite allows that
    # but init_db uses sqlite3.connect internally, so we replicate the essentials.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books_ai (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            calibre_book_id          INTEGER UNIQUE NOT NULL,
            title                    TEXT,
            author_sort              TEXT,
            authors_json             TEXT,
            tags_json                TEXT,
            series_name              TEXT,
            language                 TEXT,
            calibre_path             TEXT,
            metadata_hash            TEXT,
            formats_hash             TEXT,
            last_calibre_timestamp   TEXT,
            last_seen_at             TEXT,
            ingestion_status         TEXT NOT NULL DEFAULT 'pending',
            ingestion_error          TEXT,
            created_at               TEXT NOT NULL,
            updated_at               TEXT NOT NULL
        )
    """)
    conn.commit()
    yield conn
    conn.close()


def _insert_book(conn: sqlite3.Connection, book_id: int, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO books_ai
            (calibre_book_id, title, metadata_hash, formats_hash,
             ingestion_status, created_at, updated_at)
        VALUES (?, ?, 'h1', 'h2', ?, ?, ?)
        """,
        (book_id, f"Book {book_id}", status, now, now),
    )
    conn.commit()


class TestGetIncompleteBookIds:
    def test_pending_book_is_returned(self, mem_db):
        """Core regression: a 'pending' book must now be returned."""
        _insert_book(mem_db, book_id=1, status="pending")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 1 in result

    def test_indexed_book_is_excluded(self, mem_db):
        """Fully-indexed books must never be returned."""
        _insert_book(mem_db, book_id=2, status="indexed")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 2 not in result

    def test_failed_book_is_returned(self, mem_db):
        _insert_book(mem_db, book_id=3, status="failed")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 3 in result

    def test_extracting_book_is_returned(self, mem_db):
        _insert_book(mem_db, book_id=4, status="extracting")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 4 in result

    def test_chunked_book_is_returned(self, mem_db):
        _insert_book(mem_db, book_id=5, status="chunked")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 5 in result

    def test_mixed_statuses(self, mem_db):
        """Indexed books excluded, all others included."""
        _insert_book(mem_db, book_id=10, status="indexed")
        _insert_book(mem_db, book_id=11, status="pending")
        _insert_book(mem_db, book_id=12, status="failed")
        _insert_book(mem_db, book_id=13, status="chunked")

        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 10 not in result
        assert {11, 12, 13}.issubset(result)

    def test_empty_table_returns_empty_set(self, mem_db):
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert result == set()
