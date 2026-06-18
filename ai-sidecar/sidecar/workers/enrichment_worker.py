from __future__ import annotations

import logging
import threading

from ..ai import ChatError, get_chat_client
from ..config import get_config
from ..db.repositories import EnrichmentRepository
from ..db.session import get_db

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_draining = threading.Event()


def trigger_enrichment_drain() -> None:
    """Start a background thread that generates suggestions for queued books.

    Generates but never applies — suggestions land in the review queue. Safe to
    call repeatedly; only one drain runs at a time.
    """
    if _draining.is_set():
        return
    thread = threading.Thread(
        target=_drain_queue, name="enrichment-drain", daemon=True
    )
    thread.start()


def _drain_queue() -> None:
    if not _lock.acquire(blocking=False):
        return
    _draining.set()
    config = get_config()
    chat = get_chat_client(config)
    try:
        while True:
            with get_db() as conn:
                batch = EnrichmentRepository.get_queued(conn, limit=10)
            if not batch:
                break
            for book_id in batch:
                _process_one(config, chat, book_id)
    finally:
        _draining.clear()
        _lock.release()


def _process_one(config, chat, book_id: int) -> None:
    # Import here to avoid a circular import at module load.
    from ..api.enrichment import _generate_for_book

    with get_db() as conn:
        EnrichmentRepository.mark_queue_status(conn, book_id, "processing")
    try:
        with get_db() as conn:
            _generate_for_book(conn, config, chat, book_id)
        with get_db() as conn:
            EnrichmentRepository.mark_queue_status(conn, book_id, "done")
        logger.info("Enrichment: generated suggestion for book %d", book_id)
    except ChatError as exc:
        logger.error("Enrichment: chat unavailable for book %d: %s", book_id, exc)
        with get_db() as conn:
            EnrichmentRepository.mark_queue_status(conn, book_id, "error", str(exc))
        # Chat is down — stop draining rather than burning through the queue.
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Enrichment: failed for book %d: %s", book_id, exc)
        with get_db() as conn:
            EnrichmentRepository.mark_queue_status(conn, book_id, "error", str(exc))
