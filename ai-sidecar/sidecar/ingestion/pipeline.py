from __future__ import annotations

import logging
import threading

from ..config import get_config
from ..db.calibre_reader import CalibreReader
from ..db.repositories import BookAiRepository, FormatAiRepository, IngestionRunRepository
from ..db.session import get_db
from .scanner import compute_metadata_hash, compute_formats_hash, detect_changed_books

logger = logging.getLogger(__name__)

_running = threading.Event()


def is_running() -> bool:
    return _running.is_set()


def run_pipeline_once(run_id: int | None = None) -> None:
    """Scan Calibre metadata.db, detect changes, and update the sidecar index.

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

            # Upsert changed/new books
            for record in changed_records:
                try:
                    meta_hash = compute_metadata_hash(record)
                    fmt_hash = compute_formats_hash(record)

                    BookAiRepository.upsert(conn, record, meta_hash, fmt_hash)

                    for fmt_info in record.format_details:
                        # Calibre file path: {library_root}/{book.path}/{data.name}.{format}
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

                    changed += 1

                except Exception as exc:
                    logger.error(
                        "Failed to index book %d (%s): %s",
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
