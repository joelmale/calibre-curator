from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CalibreFormatInfo:
    format: str
    name: str                   # filename without extension (from data.name)
    uncompressed_size: int | None


@dataclass(frozen=True)
class CalibreBookRecord:
    book_id: int
    title: str
    sort: str | None
    author_sort: str | None
    path: str                   # relative path within library root, e.g. "Author/Title (42)"
    timestamp: str | None
    pubdate: str | None
    last_modified: str | None
    authors: list[str]
    tags: list[str]
    format_details: list[CalibreFormatInfo]
    series_name: str | None = None
    language: str | None = None

    @property
    def formats(self) -> list[str]:
        return [f.format for f in self.format_details]


class CalibreReader:
    def __init__(self, metadata_db: Path) -> None:
        self.metadata_db = metadata_db

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.metadata_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def count_books(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS n FROM books").fetchone()
            return int(row["n"]) if row else 0
        finally:
            conn.close()

    def list_books(self) -> Iterable[CalibreBookRecord]:
        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT
                    b.id,
                    b.title,
                    b.sort,
                    b.author_sort,
                    b.path,
                    b.timestamp,
                    b.pubdate,
                    b.last_modified
                FROM books b
                ORDER BY b.id ASC
            """).fetchall()

            for row in rows:
                book_id = int(row["id"])

                yield CalibreBookRecord(
                    book_id=book_id,
                    title=str(row["title"]),
                    sort=row["sort"],
                    author_sort=row["author_sort"],
                    path=str(row["path"]),
                    timestamp=row["timestamp"],
                    pubdate=row["pubdate"],
                    last_modified=row["last_modified"],
                    authors=self._list_authors(conn, book_id),
                    tags=self._list_tags(conn, book_id),
                    format_details=self._list_format_details(conn, book_id),
                    series_name=self._get_series(conn, book_id),
                    language=self._get_language(conn, book_id),
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Private helpers — all accept an already-open connection
    # ------------------------------------------------------------------

    def _list_authors(self, conn: sqlite3.Connection, book_id: int) -> list[str]:
        rows = conn.execute("""
            SELECT a.name
            FROM authors a
            JOIN books_authors_link bal ON bal.author = a.id
            WHERE bal.book = ?
            ORDER BY bal.id ASC
        """, (book_id,)).fetchall()
        return [str(r["name"]) for r in rows]

    def _list_tags(self, conn: sqlite3.Connection, book_id: int) -> list[str]:
        rows = conn.execute("""
            SELECT t.name
            FROM tags t
            JOIN books_tags_link btl ON btl.tag = t.id
            WHERE btl.book = ?
            ORDER BY t.name ASC
        """, (book_id,)).fetchall()
        return [str(r["name"]) for r in rows]

    def _list_format_details(
        self, conn: sqlite3.Connection, book_id: int
    ) -> list[CalibreFormatInfo]:
        rows = conn.execute("""
            SELECT d.format, d.name, d.uncompressed_size
            FROM data d
            WHERE d.book = ?
            ORDER BY d.format ASC
        """, (book_id,)).fetchall()
        return [
            CalibreFormatInfo(
                format=str(r["format"]),
                name=str(r["name"]),
                uncompressed_size=r["uncompressed_size"],
            )
            for r in rows
        ]

    def _get_series(self, conn: sqlite3.Connection, book_id: int) -> str | None:
        row = conn.execute("""
            SELECT s.name
            FROM series s
            JOIN books_series_link bsl ON bsl.series = s.id
            WHERE bsl.book = ?
            LIMIT 1
        """, (book_id,)).fetchone()
        return str(row["name"]) if row else None

    def _get_language(self, conn: sqlite3.Connection, book_id: int) -> str | None:
        # Calibre uses "lang_code" as both the FK column name in
        # books_languages_link and the value column in languages.
        row = conn.execute("""
            SELECT l.lang_code
            FROM languages l
            JOIN books_languages_link bll ON bll.lang_code = l.id
            WHERE bll.book = ?
            LIMIT 1
        """, (book_id,)).fetchone()
        return str(row["lang_code"]) if row else None
