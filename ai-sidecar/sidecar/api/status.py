from __future__ import annotations

from flask import Blueprint, jsonify

from ..config import get_config
from ..db.calibre_reader import CalibreReader
from ..db.repositories import IngestionRunRepository
from ..db.session import get_db
from ..security import require_bearer_token

status_bp = Blueprint("status", __name__)


@status_bp.route("/status")
@require_bearer_token
def get_status():
    config = get_config()

    db_readable = config.calibre_metadata_db.exists()
    calibre_count = 0
    if db_readable:
        try:
            calibre_count = CalibreReader(config.calibre_metadata_db).count_books()
        except Exception:
            db_readable = False

    indexed_count = 0
    last_run = None
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM books_ai WHERE ingestion_status = 'indexed'"
        ).fetchone()
        indexed_count = row["n"] if row else 0
        last_run = IngestionRunRepository.get_latest(conn)

    embedding_model = (
        config.ollama_embed_model
        if config.embedding_provider == "ollama"
        else config.openai_embed_model
    )

    return jsonify({
        "library": {
            "metadataDbReadable": db_readable,
            "bookCount":          calibre_count,
            "indexedBookCount":   indexed_count,
            "pendingBookCount":   max(0, calibre_count - indexed_count),
        },
        "embedding": {
            "provider": config.embedding_provider,
            "model":    embedding_model,
        },
        "lastIngestionRun": last_run,
    })
