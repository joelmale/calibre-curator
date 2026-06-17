from __future__ import annotations

from flask import Blueprint, jsonify

from ..config import get_config
from ..db.session import get_db
from ..security import require_bearer_token

status_bp = Blueprint("status", __name__)


@status_bp.route("/status")
@require_bearer_token
def get_status():
    config = get_config()
    db_readable = config.calibre_metadata_db.exists()
    book_count = 0
    indexed_count = 0
    last_run = None

    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM books_ai").fetchone()
        book_count = row["n"] if row else 0

        row = conn.execute(
            "SELECT COUNT(*) AS n FROM books_ai WHERE ingestion_status = 'indexed'"
        ).fetchone()
        indexed_count = row["n"] if row else 0

        run_row = conn.execute(
            "SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if run_row:
            last_run = dict(run_row)

    embedding_model = (
        config.ollama_embed_model
        if config.embedding_provider == "ollama"
        else config.openai_embed_model
    )

    return jsonify({
        "library": {
            "metadataDbReadable": db_readable,
            "bookCount": book_count,
            "indexedBookCount": indexed_count,
            "pendingBookCount": book_count - indexed_count,
        },
        "embedding": {
            "provider": config.embedding_provider,
            "model": embedding_model,
        },
        "lastIngestionRun": last_run,
    })
