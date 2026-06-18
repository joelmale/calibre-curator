from __future__ import annotations

import logging
import threading

from ..config import get_config
from ..db.calibre_reader import CalibreReader
from ..db.repositories import BookAiRepository, ChunkRepository, FormatAiRepository, IngestionRunRepository
from ..db.session import get_db
from .chunker import chunk_text
from .extractor import extract_text
from .scanner import compute_formats_hash, compute_metadata_hash, detect_changed_books

logger = logging.getLogger(__name__)

_running = threading.Event()


def is_running() -> bool:
    return _running.is_set()


def run_pipeline_once(run_id: int | None = None) -> None:
    """Scan Calibre metadata.db, extract text, chunk, and update the sidecar index.

    Safe to call from both the APScheduler background job and the API endpoint.
    Concurrent calls are no-ops (returns immediately if already running).
    """
    if not _running.is_set():
        _running.set()
    else:
        logger.info("Ingestion pipeline already running — skipping concurrent call")
        return

    try:
        _do_run(run_id)
    finally:
        _running.clear()


def _do_run(run_id: int | None) -> None:
    config = get_config()

    if not config.calibre_metadata_db.exists():
        logger.warning(
            "Calibre metadata.db not found at %s — skipping run",
            config.calibre_metadata_db,
        )
        return

    reader = CalibreReader(config.calibre_metadata_db)
    scanned = 0
    changed = 0
    errors = 0

    with get_db() as conn:
        if run_id is None:
            run_id = IngestionRunRepository.start(conn)

        try:
            all_records = list(reader.list_books())
            scanned = len(all_records)

            known = BookAiRepository.get_known_book_ids(conn)
            changed_records, _ = detect_changed_books(all_records, known)

            # Remove books no longer present in Calibre
            current_ids = {r.book_id for r in all_records}
            removed = BookAiRepository.delete_removed(conn, current_ids)
            if removed:
                logger.info("Removed %d stale book(s) from index", removed)

            for record in changed_records:
                try:
                    meta_hash = compute_metadata_hash(record)
                    fmt_hash = compute_formats_hash(record)

                    BookAiRepository.upsert(conn, record, meta_hash, fmt_hash)
                    BookAiRepository.mark_status(conn, record.book_id, "extracting")

                    # Delete stale chunks so re-extraction is clean
                    ChunkRepository.delete_for_book(conn, record.book_id)

                    best_text = ""
                    best_source = ""

                    for fmt_info in record.format_details:
                        relative_path = (
                            f"{record.path}/{fmt_info.name}.{fmt_info.format.lower()}"
                        )
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

                        # Prefer the format with the most text
                        if result.ok and len(result.text) > len(best_text):
                            best_text = result.text
                            best_source = result.source

                    if best_text.strip():
                        chunks = chunk_text(best_text, record.book_id)
                        ChunkRepository.insert_batch(
                            conn, record.book_id, best_source, chunks
                        )
                        logger.debug(
                            "Book %d: extracted %d chars → %d chunks",
                            record.book_id, len(best_text), len(chunks),
                        )
                        BookAiRepository.mark_status(conn, record.book_id, "chunked")
                    else:
                        BookAiRepository.mark_status(
                            conn, record.book_id, "failed", "no extractable text"
                        )

                    changed += 1

                except Exception as exc:
                    logger.error(
                        "Failed to process book %d (%s): %s",
                        record.book_id, record.title, exc,
                    )
                    BookAiRepository.mark_status(
                        conn, record.book_id, "failed", str(exc)
                    )
                    errors += 1

            status = "completed" if errors == 0 else "partial"
            IngestionRunRepository.finish(
                conn, run_id,
                status=status,
                scanned=scanned,
                changed=changed,
                embedded=0,
                errors=errors,
            )

            logger.info(
                "Ingestion run #%d: %d scanned, %d changed, %d errors — %s",
                run_id, scanned, changed, errors, status,
            )

        except Exception as exc:
            logger.exception("Ingestion run #%d failed unexpectedly: %s", run_id, exc)
            IngestionRunRepository.finish(
                conn, run_id,
                status="failed",
                scanned=scanned,
                changed=changed,
                embedded=0,
                errors=errors + 1,
            )
