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
            all_records = list(reader.list_books())
            scanned = len(all_records)

            known = BookAiRepository.get_known_book_ids(conn)
            changed_records, _ = detect_changed_books(all_records, known)

            if limit is not None and limit > 0:
                changed_records = changed_records[:limit]
                logger.info("Limiting run to first %d changed book(s)", limit)

            current_ids = {r.book_id for r in all_records}
            removed_count = BookAiRepository.delete_removed(conn, current_ids)
            if removed_count:
                logger.info("Removed %d stale book(s) from index", removed_count)

            for record in changed_records:
                try:
                    _process_book(conn, record, config, provider, store)
                    changed += 1
                except Exception as exc:
                    logger.error(
                        "Failed to process book %d (%s): %s",
                        record.book_id, record.title, exc,
                    )
                    BookAiRepository.mark_status(conn, record.book_id, "failed", str(exc))
                    errors += 1

            # Embed any chunks that are still pending (e.g. from a previous
            # failed run that chunked but didn't finish embedding)
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
                "Ingestion run #%d: %d scanned, %d changed, %d embedded, %d errors — %s",
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
    logger.debug("Book %d: %d chunks written", record.book_id, len(chunks))


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
            vectors = provider.embed(texts)
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
