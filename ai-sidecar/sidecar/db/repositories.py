from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .calibre_reader import CalibreBookRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BookAiRepository:
    @staticmethod
    def get_known_book_ids(
        conn: sqlite3.Connection,
    ) -> dict[int, tuple[str, str]]:
        """Returns {calibre_book_id: (metadata_hash, formats_hash)} for all tracked books."""
        rows = conn.execute(
            "SELECT calibre_book_id, metadata_hash, formats_hash FROM books_ai"
        ).fetchall()
        return {
            int(r["calibre_book_id"]): (r["metadata_hash"], r["formats_hash"])
            for r in rows
        }

    @staticmethod
    def upsert(
        conn: sqlite3.Connection,
        record: CalibreBookRecord,
        metadata_hash: str,
        formats_hash: str,
    ) -> None:
        now = _now()
        conn.execute("""
            INSERT INTO books_ai (
                calibre_book_id, title, author_sort, authors_json, tags_json,
                series_name, language, calibre_path,
                metadata_hash, formats_hash,
                last_calibre_timestamp, last_seen_at,
                ingestion_status,
                created_at, updated_at
            ) VALUES (
                :book_id, :title, :author_sort, :authors_json, :tags_json,
                :series_name, :language, :path,
                :metadata_hash, :formats_hash,
                :last_modified, :now,
                'pending',
                :now, :now
            )
            ON CONFLICT(calibre_book_id) DO UPDATE SET
                title                   = excluded.title,
                author_sort             = excluded.author_sort,
                authors_json            = excluded.authors_json,
                tags_json               = excluded.tags_json,
                series_name             = excluded.series_name,
                language                = excluded.language,
                calibre_path            = excluded.calibre_path,
                metadata_hash           = excluded.metadata_hash,
                formats_hash            = excluded.formats_hash,
                last_calibre_timestamp  = excluded.last_calibre_timestamp,
                last_seen_at            = excluded.last_seen_at,
                ingestion_status        = 'pending',
                ingestion_error         = NULL,
                updated_at              = excluded.updated_at
        """, {
            "book_id":        record.book_id,
            "title":          record.title,
            "author_sort":    record.author_sort,
            "authors_json":   json.dumps(record.authors),
            "tags_json":      json.dumps(record.tags),
            "series_name":    record.series_name,
            "language":       record.language,
            "path":           record.path,
            "metadata_hash":  metadata_hash,
            "formats_hash":   formats_hash,
            "last_modified":  record.last_modified,
            "now":            now,
        })

    @staticmethod
    def get_incomplete_book_ids(conn: sqlite3.Connection) -> set[int]:
        """Return IDs of all non-indexed books so they are retried on every run.

        Lifecycle: books enter as 'pending' (upsert), advance through
        'extracting' → 'chunked' → 'indexed' as the pipeline progresses, or
        land on 'failed' if an error occurs.  We include 'pending' here so
        that books which were inserted in a prior scan but never processed
        (the common stuck state) are always re-queued.  Within a single run,
        processed books reach 'indexed' or 'failed' before the next run
        starts, so including 'pending' causes no harmful double-processing.
        """
        rows = conn.execute(
            "SELECT calibre_book_id FROM books_ai "
            "WHERE ingestion_status != 'indexed'"
        ).fetchall()
        return {int(r["calibre_book_id"]) for r in rows}

    @staticmethod
    def get_recent_failures(
        conn: sqlite3.Connection, limit: int = 25
    ) -> list[sqlite3.Row]:
        """Return the most recently-updated books with ingestion_status='failed'."""
        return conn.execute(
            """
            SELECT calibre_book_id, title, ingestion_error, updated_at
            FROM books_ai
            WHERE ingestion_status = 'failed'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    @staticmethod
    def get_status_breakdown(conn: sqlite3.Connection) -> dict[str, int]:
        rows = conn.execute(
            "SELECT ingestion_status, COUNT(*) AS n FROM books_ai GROUP BY ingestion_status"
        ).fetchall()
        return {r["ingestion_status"]: r["n"] for r in rows}

    @staticmethod
    def delete_removed(conn: sqlite3.Connection, current_ids: set[int]) -> int:
        """Delete any tracked books whose ID is not in current_ids. Returns count deleted."""
        if not current_ids:
            result = conn.execute("DELETE FROM books_ai")
            return result.rowcount
        placeholders = ",".join("?" * len(current_ids))
        result = conn.execute(
            f"DELETE FROM books_ai WHERE calibre_book_id NOT IN ({placeholders})",
            list(current_ids),
        )
        return result.rowcount

    @staticmethod
    def mark_status(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        conn.execute("""
            UPDATE books_ai
            SET ingestion_status = ?, ingestion_error = ?, updated_at = ?
            WHERE calibre_book_id = ?
        """, (status, error, _now(), calibre_book_id))


class FormatAiRepository:
    @staticmethod
    def upsert(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        fmt: str,
        relative_path: str,
        file_size_bytes: int | None = None,
        mtime_ns: int | None = None,
    ) -> None:
        conn.execute("""
            INSERT INTO book_formats_ai (
                calibre_book_id, format, relative_path,
                file_size_bytes, mtime_ns, extraction_status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(calibre_book_id, format) DO UPDATE SET
                relative_path       = excluded.relative_path,
                file_size_bytes     = excluded.file_size_bytes,
                mtime_ns            = excluded.mtime_ns,
                extraction_status   = 'pending',
                extraction_error    = NULL
        """, (calibre_book_id, fmt, relative_path, file_size_bytes, mtime_ns))

    @staticmethod
    def mark_extraction(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        fmt: str,
        status: str,
        error: str | None = None,
    ) -> None:
        conn.execute("""
            UPDATE book_formats_ai
            SET extraction_status = ?,
                extraction_error  = ?,
                extracted_at      = ?
            WHERE calibre_book_id = ? AND format = ?
        """, (status, error, _now(), calibre_book_id, fmt))


class ChunkRepository:
    @staticmethod
    def delete_for_book(conn: sqlite3.Connection, calibre_book_id: int) -> None:
        conn.execute(
            "DELETE FROM book_chunks WHERE calibre_book_id = ?",
            (calibre_book_id,),
        )

    @staticmethod
    def insert_batch(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        source_type: str,
        chunks: list,
    ) -> None:
        now = _now()
        conn.executemany("""
            INSERT INTO book_chunks (
                calibre_book_id, chunk_uid, source_type,
                chunk_index, heading, text, token_estimate,
                char_start, char_end, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                calibre_book_id,
                c.chunk_uid,
                source_type,
                c.chunk_index,
                c.heading,
                c.text,
                c.token_estimate,
                c.char_start,
                c.char_end,
                now,
            )
            for c in chunks
        ])

    @staticmethod
    def get_unembedded(
        conn: sqlite3.Connection,
        limit: int = 500,
    ) -> list[sqlite3.Row]:
        return conn.execute("""
            SELECT chunk_uid, calibre_book_id, text, heading
            FROM book_chunks
            WHERE vector_id IS NULL
            ORDER BY calibre_book_id, chunk_index
            LIMIT ?
        """, (limit,)).fetchall()

    @staticmethod
    def get_book_chunks(
        conn: sqlite3.Connection,
        calibre_book_id: int,
    ) -> list[sqlite3.Row]:
        return conn.execute("""
            SELECT chunk_uid, text, heading
            FROM book_chunks
            WHERE calibre_book_id = ?
            ORDER BY chunk_index
        """, (calibre_book_id,)).fetchall()

    @staticmethod
    def mark_embedded_batch(
        conn: sqlite3.Connection,
        chunk_uids: list[str],
        model_name: str,
    ) -> None:
        now = _now()
        conn.executemany("""
            UPDATE book_chunks
            SET vector_id = chunk_uid, embedding_model = ?, embedded_at = ?
            WHERE chunk_uid = ?
        """, [(model_name, now, uid) for uid in chunk_uids])


class BookAiLookup:
    @staticmethod
    def get_by_ids(
        conn: sqlite3.Connection,
        calibre_book_ids: list[int],
    ) -> dict[int, sqlite3.Row]:
        if not calibre_book_ids:
            return {}
        placeholders = ",".join("?" * len(calibre_book_ids))
        rows = conn.execute(
            f"SELECT * FROM books_ai WHERE calibre_book_id IN ({placeholders})",
            calibre_book_ids,
        ).fetchall()
        return {int(r["calibre_book_id"]): r for r in rows}


class EnrichmentRepository:
    """Feature 4 — auto-tagging / metadata enrichment."""

    @staticmethod
    def get_candidates(
        conn: sqlite3.Connection, limit: int = 50
    ) -> list[sqlite3.Row]:
        """Indexed books that lack tags and have no suggestion yet."""
        return conn.execute(
            """
            SELECT b.calibre_book_id, b.title, b.author_sort, b.tags_json
            FROM books_ai b
            WHERE b.ingestion_status = 'indexed'
              AND (b.tags_json IS NULL OR b.tags_json IN ('[]', ''))
              AND NOT EXISTS (
                  SELECT 1 FROM enrichment_suggestions s
                  WHERE s.calibre_book_id = b.calibre_book_id
              )
            ORDER BY b.calibre_book_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    @staticmethod
    def count_candidates(conn: sqlite3.Connection) -> int:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM books_ai b
            WHERE b.ingestion_status = 'indexed'
              AND (b.tags_json IS NULL OR b.tags_json IN ('[]', ''))
              AND NOT EXISTS (
                  SELECT 1 FROM enrichment_suggestions s
                  WHERE s.calibre_book_id = b.calibre_book_id
              )
            """
        ).fetchone()
        return int(row["n"]) if row else 0

    @staticmethod
    def get_book_text(
        conn: sqlite3.Connection, calibre_book_id: int, max_chars: int
    ) -> str:
        """Concatenate the book's chunks (in order) up to max_chars."""
        rows = conn.execute(
            """
            SELECT text FROM book_chunks
            WHERE calibre_book_id = ?
            ORDER BY chunk_index ASC
            """,
            (calibre_book_id,),
        ).fetchall()
        out: list[str] = []
        total = 0
        for r in rows:
            t = r["text"] or ""
            out.append(t)
            total += len(t)
            if total >= max_chars:
                break
        return "\n\n".join(out)[:max_chars]

    @staticmethod
    def upsert_suggestion(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        tags: list[str],
        description: str | None,
        reading_level: str | None,
        confidence: float | None,
        chat_model: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO enrichment_suggestions (
                calibre_book_id, suggested_tags_json, suggested_description,
                suggested_reading_level, confidence, chat_model,
                review_status, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(calibre_book_id) DO UPDATE SET
                suggested_tags_json     = excluded.suggested_tags_json,
                suggested_description   = excluded.suggested_description,
                suggested_reading_level = excluded.suggested_reading_level,
                confidence              = excluded.confidence,
                chat_model              = excluded.chat_model,
                review_status           = 'pending',
                generated_at            = excluded.generated_at
            """,
            (
                calibre_book_id,
                json.dumps(tags),
                description,
                reading_level,
                confidence,
                chat_model,
                _now(),
            ),
        )

    @staticmethod
    def get_suggestion(
        conn: sqlite3.Connection, calibre_book_id: int
    ) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM enrichment_suggestions WHERE calibre_book_id = ?",
            (calibre_book_id,),
        ).fetchone()

    @staticmethod
    def get_pending_suggestions(
        conn: sqlite3.Connection, limit: int = 100
    ) -> list[sqlite3.Row]:
        """Pending suggestions joined with the book's current metadata."""
        return conn.execute(
            """
            SELECT s.*, b.title, b.author_sort, b.tags_json AS current_tags_json
            FROM enrichment_suggestions s
            JOIN books_ai b ON b.calibre_book_id = s.calibre_book_id
            WHERE s.review_status = 'pending'
            ORDER BY s.confidence DESC NULLS LAST, s.generated_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    @staticmethod
    def mark_suggestion_reviewed(
        conn: sqlite3.Connection, calibre_book_id: int, status: str = "reviewed"
    ) -> None:
        conn.execute(
            "UPDATE enrichment_suggestions SET review_status = ? WHERE calibre_book_id = ?",
            (status, calibre_book_id),
        )

    # ── Queue (background pre-generation) ────────────────────────────────────

    @staticmethod
    def enqueue(conn: sqlite3.Connection, calibre_book_ids: list[int]) -> int:
        if not calibre_book_ids:
            return 0
        conn.executemany(
            """
            INSERT INTO enrichment_queue (calibre_book_id, status, queued_at, updated_at)
            VALUES (?, 'queued', ?, ?)
            ON CONFLICT(calibre_book_id) DO NOTHING
            """,
            [(bid, _now(), _now()) for bid in calibre_book_ids],
        )
        return len(calibre_book_ids)

    @staticmethod
    def get_queued(conn: sqlite3.Connection, limit: int = 20) -> list[int]:
        rows = conn.execute(
            "SELECT calibre_book_id FROM enrichment_queue "
            "WHERE status = 'queued' ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [int(r["calibre_book_id"]) for r in rows]

    @staticmethod
    def mark_queue_status(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        conn.execute(
            "UPDATE enrichment_queue SET status = ?, error = ?, updated_at = ? "
            "WHERE calibre_book_id = ?",
            (status, error, _now(), calibre_book_id),
        )

    # ── Reviews / applied audit log ──────────────────────────────────────────

    @staticmethod
    def insert_review(
        conn: sqlite3.Connection,
        calibre_book_id: int,
        applied_tags: list[str] | None,
        applied_description: str | None,
        applied_reading_level: str | None,
        decision: dict,
        writeback_status: str,
        writeback_error: str | None = None,
        reviewer: str = "admin",
    ) -> None:
        conn.execute(
            """
            INSERT INTO enrichment_reviews (
                calibre_book_id, applied_tags_json, applied_description,
                applied_reading_level, decision_json, reviewer,
                writeback_status, writeback_error, applied_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                calibre_book_id,
                json.dumps(applied_tags) if applied_tags is not None else None,
                applied_description,
                applied_reading_level,
                json.dumps(decision),
                reviewer,
                writeback_status,
                writeback_error,
                _now(),
            ),
        )

    @staticmethod
    def get_reviews(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT r.*, b.title, b.author_sort
            FROM enrichment_reviews r
            LEFT JOIN books_ai b ON b.calibre_book_id = r.calibre_book_id
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


class ProviderSettingsRepository:
    """Per-provider rate-limit settings for the chat fallback chain."""

    @staticmethod
    def get_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return conn.execute(
            "SELECT provider, rpm, rph, enabled FROM provider_rate_limits"
        ).fetchall()

    @staticmethod
    def upsert(
        conn: sqlite3.Connection,
        provider: str,
        rpm: int | None,
        rph: int | None,
        enabled: bool,
    ) -> None:
        conn.execute(
            """
            INSERT INTO provider_rate_limits (provider, rpm, rph, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                rpm        = excluded.rpm,
                rph        = excluded.rph,
                enabled    = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (provider, rpm, rph, 1 if enabled else 0, _now()),
        )


class CollectionRepository:
    """Curated collections — used by the Sequence Builder (Feature 3)."""

    @staticmethod
    def save(
        conn: sqlite3.Connection,
        collection_slug: str,
        title: str,
        description: str,
        collection_type: str,
        generation_prompt: str | None,
        items: list[tuple[int, int, float, str]],
    ) -> None:
        """Upsert a collection and replace its items.

        items — list of (calibre_book_id, rank, score, match_reason).
        """
        now = _now()
        conn.execute(
            """
            INSERT INTO curated_collections (
                collection_slug, title, description, collection_type,
                generation_prompt, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_slug) DO UPDATE SET
                title             = excluded.title,
                description       = excluded.description,
                collection_type   = excluded.collection_type,
                generation_prompt = excluded.generation_prompt,
                updated_at        = excluded.updated_at
            """,
            (collection_slug, title, description, collection_type,
             generation_prompt, now, now),
        )
        conn.execute(
            "DELETE FROM curated_collection_items WHERE collection_slug = ?",
            (collection_slug,),
        )
        conn.executemany(
            """
            INSERT INTO curated_collection_items (
                collection_slug, calibre_book_id, rank, score, match_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(collection_slug, bid, rank, score, reason, now)
             for (bid, rank, score, reason) in items],
        )

    @staticmethod
    def list_by_type(
        conn: sqlite3.Connection, collection_type: str
    ) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT c.collection_slug, c.title, c.description, c.collection_type,
                   c.generation_prompt, c.updated_at,
                   (SELECT COUNT(*) FROM curated_collection_items i
                    WHERE i.collection_slug = c.collection_slug) AS item_count
            FROM curated_collections c
            WHERE c.collection_type = ?
            ORDER BY c.updated_at DESC
            """,
            (collection_type,),
        ).fetchall()

    @staticmethod
    def get_items(
        conn: sqlite3.Connection, collection_slug: str
    ) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT i.calibre_book_id, i.rank, i.score, i.match_reason,
                   b.title, b.author_sort, b.authors_json
            FROM curated_collection_items i
            LEFT JOIN books_ai b ON b.calibre_book_id = i.calibre_book_id
            WHERE i.collection_slug = ?
            ORDER BY i.rank ASC
            """,
            (collection_slug,),
        ).fetchall()


class IngestionRunRepository:
    @staticmethod
    def start(conn: sqlite3.Connection) -> int:
        cursor = conn.execute("""
            INSERT INTO ingestion_runs (started_at, status)
            VALUES (?, 'running')
        """, (_now(),))
        return int(cursor.lastrowid)

    @staticmethod
    def finish(
        conn: sqlite3.Connection,
        run_id: int,
        status: str,
        scanned: int,
        changed: int,
        embedded: int,
        errors: int,
    ) -> None:
        conn.execute("""
            UPDATE ingestion_runs
            SET finished_at     = ?,
                status          = ?,
                scanned_books   = ?,
                changed_books   = ?,
                embedded_chunks = ?,
                error_count     = ?
            WHERE id = ?
        """, (_now(), status, scanned, changed, embedded, errors, run_id))

    @staticmethod
    def get_latest(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {
            "runId":          row["id"],
            "startedAt":      row["started_at"],
            "finishedAt":     row["finished_at"],
            "status":         row["status"],
            "scannedBooks":   row["scanned_books"],
            "changedBooks":   row["changed_books"],
            "embeddedChunks": row["embedded_chunks"],
            "errorCount":     row["error_count"],
        }
