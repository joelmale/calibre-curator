from __future__ import annotations

import logging
import threading

from ..config import get_config
from ..db.calibre_reader import CalibreReader
from ..db.repositories import (
    BookAiRepository,
    ChunkRepository,
    FormatAiRepository,
    IngestionRunRepository,
)

# All non-indexed books are re-queued on every run (pending, failed,
# extracting, chunked).  This ensures books that were registered but never
# processed ('pending') converge to 'indexed' rather than being skipped
# forever by the changed-book detector.
_RETRY_STATUSES = frozenset({"pending", "failed", "extracting", "chunked"})
from ..db.session import get_db
from ..embeddings import get_embedding_provider
from ..vectors import get_vector_store
from .chunker import chunk_text
from .extractor import extract_text
from .scanner import compute_formats_hash, compute_metadata_hash, detect_changed_books

logger = logging.getLogger(__name__)

_running = threading.Event()

_EMBED_BATCH = 32


def is_running() -> bool:
    return _running.is_set()


def run_pipeline_once(run_id: int | None = None, limit: int | None = None) -> None:
    """Scan Calibre, extract text, chunk, embed, and index into the vector store.

    limit — cap how many changed books are processed in this run (None = all).
    Safe to call from APScheduler and the API endpoint concurrently — extra
    calls are no-ops while a run is in progress.
    """
    if not _running.is_set():
        _running.set()
    else:
        logger.info("Ingestion pipeline already running — skipping concurrent call")
        return

    try:
        _do_run(run_id, limit=limit)
    finally:
        _running.clear()


def _do_run(run_id: int | None, limit: int | None = None) -> None:
    config = get_config()

    if not config.calibre_metadata_db.exists():
        logger.warning(
            "Calibre metadata.db not found at %s — skipping run",
            config.calibre_metadata_db,
        )
        return

    provider = get_embedding_provider(config)
    store = get_vector_store(config, provider.model_name)
    reader = CalibreReader(config.calibre_metadata_db)

    scanned = 0
    changed = 0
    embedded = 0
    errors = 0

    with get_db() as conn:
        if run_id is None:
            run_id = IngestionRunRepository.start(conn)

        try:
            logger.info("Run #%d — scanning Calibre library at %s", run_id, config.calibre_metadata_db)
            all_records = list(reader.list_books())
            scanned = len(all_records)
            logger.info("Run #%d — found %d books in library", run_id, scanned)

            known = BookAiRepository.get_known_book_ids(conn)
            changed_records, _ = detect_changed_books(all_records, known)

            # Re-queue all non-indexed books (pending, failed, extracting, chunked).
            # This is the convergence path: books stuck at 'pending' that were
            # registered in a prior scan but never reached 'indexed' are picked
            # up here rather than being skipped by the changed-book detector.
            incomplete_ids = BookAiRepository.get_incomplete_book_ids(conn)
            if incomplete_ids:
                already_queued = {r.book_id for r in changed_records}
                retry_records = [
                    r for r in all_records
                    if r.book_id in incomplete_ids and r.book_id not in already_queued
                ]
                if retry_records:
                    logger.info(
                        "Run #%d — %d book(s) pending/incomplete → queued for processing",
                        run_id, len(retry_records),
                    )
                changed_records = changed_records + retry_records

            logger.info("Run #%d — %d book(s) new or changed (incl. retries)", run_id, len(changed_records))

            if limit is not None and limit > 0:
                changed_records = changed_records[:limit]
                logger.info("Run #%d — limiting to first %d book(s)", run_id, limit)

            current_ids = {r.book_id for r in all_records}
            removed_count = BookAiRepository.delete_removed(conn, current_ids)
            if removed_count:
                logger.info("Run #%d — removed %d stale book(s) from index", run_id, removed_count)

            total_to_process = len(changed_records)
            for idx, record in enumerate(changed_records, 1):
                logger.info(
                    "Run #%d — [%d/%d] processing book %d: %s",
                    run_id, idx, total_to_process, record.book_id, record.title,
                )
                try:
                    _process_book(conn, record, config, provider, store)
                    changed += 1
                except Exception as exc:
                    logger.error(
                        "Run #%d — failed book %d (%s): %s",
                        run_id, record.book_id, record.title, exc,
                    )
                    BookAiRepository.mark_status(conn, record.book_id, "failed", str(exc))
                    errors += 1

            logger.info("Run #%d — embedding pending chunks…", run_id)
            embedded = _embed_pending(conn, provider, store)

            status = "completed" if errors == 0 else "partial"
            IngestionRunRepository.finish(
                conn, run_id,
                status=status,
                scanned=scanned,
                changed=changed,
                embedded=embedded,
                errors=errors,
            )
            logger.info(
                "Run #%d done — %d scanned, %d changed, %d embedded, %d errors — %s",
                run_id, scanned, changed, embedded, errors, status,
            )

        except Exception as exc:
            logger.exception("Ingestion run #%d failed unexpectedly: %s", run_id, exc)
            IngestionRunRepository.finish(
                conn, run_id,
                status="failed",
                scanned=scanned,
                changed=changed,
                embedded=embedded,
                errors=errors + 1,
            )


def _process_book(conn, record, config, provider, store) -> None:
    meta_hash = compute_metadata_hash(record)
    fmt_hash = compute_formats_hash(record)

    BookAiRepository.upsert(conn, record, meta_hash, fmt_hash)
    BookAiRepository.mark_status(conn, record.book_id, "extracting")

    # Delete stale chunks and vectors before re-processing
    ChunkRepository.delete_for_book(conn, record.book_id)
    store.delete_by_book_id(record.book_id)

    best_text = ""
    best_source = ""

    for fmt_info in record.format_details:
        relative_path = f"{record.path}/{fmt_info.name}.{fmt_info.format.lower()}"
        FormatAiRepository.upsert(
            conn,
            calibre_book_id=record.book_id,
            fmt=fmt_info.format,
            relative_path=relative_path,
            file_size_bytes=fmt_info.uncompressed_size,
        )
        result = extract_text(
            library_root=config.calibre_library_root,
            relative_path=relative_path,
            fmt=fmt_info.format,
            max_chars=config.max_extracted_chars_per_book,
        )
        FormatAiRepository.mark_extraction(
            conn,
            calibre_book_id=record.book_id,
            fmt=fmt_info.format,
            status="extracted" if result.ok else "failed",
            error=result.error,
        )
        if result.ok and len(result.text) > len(best_text):
            best_text = result.text
            best_source = result.source

    if not best_text.strip():
        BookAiRepository.mark_status(conn, record.book_id, "failed", "no extractable text")
        return

    chunks = chunk_text(best_text, record.book_id)
    ChunkRepository.insert_batch(conn, record.book_id, best_source, chunks)
    BookAiRepository.mark_status(conn, record.book_id, "chunked")
    logger.info("Book %d: extracted %d chars from %s, wrote %d chunks", record.book_id, len(best_text), best_source, len(chunks))


def _embed_pending(conn, provider, store) -> int:
    """Embed all chunks that have no vector_id yet. Returns count embedded."""
    total = 0
    while True:
        rows = ChunkRepository.get_unembedded(conn, limit=_EMBED_BATCH)
        if not rows:
            break

        texts = [r["text"] for r in rows]
        uids = [r["chunk_uid"] for r in rows]
        book_ids = [int(r["calibre_book_id"]) for r in rows]
        headings = [r["heading"] for r in rows]

        try:
            vectors = provider.embed_documents(texts)
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            break

        store.upsert(
            ids=uids,
            embeddings=vectors,
            metadatas=[
                {"calibre_book_id": bid, "heading": h or ""}
                for bid, h in zip(book_ids, headings)
            ],
            documents=texts,
        )
        ChunkRepository.mark_embedded_batch(conn, uids, provider.model_name)
        logger.info("Embedded batch of %d chunks (total so far: %d)", len(uids), total + len(uids))

        # Mark books as fully indexed once all their chunks are embedded
        for book_id in set(book_ids):
            remaining = conn.execute(
                "SELECT COUNT(*) FROM book_chunks WHERE calibre_book_id = ? AND vector_id IS NULL",
                (book_id,),
            ).fetchone()[0]
            if remaining == 0:
                BookAiRepository.mark_status(conn, book_id, "indexed")

        total += len(uids)
        if len(rows) < _EMBED_BATCH:
            break

    return total
