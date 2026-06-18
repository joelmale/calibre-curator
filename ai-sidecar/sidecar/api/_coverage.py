"""Shared helper to report vector index coverage counts."""
from __future__ import annotations

import logging

from ..config import Config
from ..db.calibre_reader import CalibreReader
from ..db.session import get_db

logger = logging.getLogger(__name__)


def get_index_coverage(config: Config) -> dict:
    """Return {indexedBookCount, totalBooks} for surfacing index completeness."""
    indexed_count = 0
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM books_ai WHERE ingestion_status = 'indexed'"
        ).fetchone()
        indexed_count = row["n"] if row else 0

    total_books = 0
    if config.calibre_metadata_db.exists():
        try:
            total_books = CalibreReader(config.calibre_metadata_db).count_books()
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not count Calibre books: %s", exc)

    return {"indexedBookCount": indexed_count, "totalBooks": total_books}
