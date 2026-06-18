"""Unit tests for BookAiRepository.get_incomplete_book_ids.

Verifies that the fix for the stuck-indexing bug works correctly:
- 'pending' and 'extracting' books ARE returned
- 'indexed', 'failed', and 'chunked' books are NOT returned
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
    import importlib.resources as ir
    from pathlib import Path
    from sidecar.db import schema as schema_mod
    import inspect, re
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
        _insert_book(mem_db, book_id=1, status="pending")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 1 in result

    def test_indexed_book_is_excluded(self, mem_db):
        _insert_book(mem_db, book_id=2, status="indexed")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 2 not in result

    def test_failed_book_is_excluded(self, mem_db):
        _insert_book(mem_db, book_id=3, status="failed")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 3 not in result

    def test_extracting_book_is_returned(self, mem_db):
        _insert_book(mem_db, book_id=4, status="extracting")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 4 in result

    def test_chunked_book_is_excluded(self, mem_db):
        _insert_book(mem_db, book_id=5, status="chunked")
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 5 not in result

    def test_mixed_statuses(self, mem_db):
        _insert_book(mem_db, book_id=10, status="indexed")
        _insert_book(mem_db, book_id=11, status="pending")
        _insert_book(mem_db, book_id=12, status="failed")
        _insert_book(mem_db, book_id=13, status="chunked")

        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert 10 not in result
        assert 11 in result
        assert 12 not in result
        assert 13 not in result

    def test_empty_table_returns_empty_set(self, mem_db):
        result = BookAiRepository.get_incomplete_book_ids(mem_db)
        assert result == set()

