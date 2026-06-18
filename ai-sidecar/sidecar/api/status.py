from __future__ import annotations

from flask import Blueprint, jsonify

import requests

from ..config import get_config
from ..db.calibre_reader import CalibreReader
from ..db.repositories import BookAiRepository, IngestionRunRepository
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
    status_breakdown: dict[str, int] = {}
    last_run = None
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM books_ai WHERE ingestion_status = 'indexed'"
        ).fetchone()
        indexed_count = row["n"] if row else 0
        status_breakdown = BookAiRepository.get_status_breakdown(conn)
        last_run = IngestionRunRepository.get_latest(conn)

    embedding_model = (
        config.ollama_embed_model
        if config.embedding_provider == "ollama"
        else config.openai_embed_model
    )

    # Quick reachability probe: check Ollama /api/tags to see if the model is available
    embedding_ok = True
    embedding_warning: str | None = None
    if config.embedding_provider == "ollama":
        try:
            resp = requests.get(
                f"{config.ollama_base_url}/api/tags", timeout=3
            )
            if resp.ok:
                available = [m["name"] for m in resp.json().get("models", [])]
                short_name = embedding_model.split(":")[0]
                if not any(
                    m == embedding_model or m.startswith(short_name + ":")
                    for m in available
                ):
                    embedding_ok = False
                    embedding_warning = (
                        f"Model '{embedding_model}' is not pulled. "
                        f"Run: ollama pull {embedding_model}"
                    )
            else:
                embedding_warning = f"Ollama unreachable ({resp.status_code})"
        except Exception as exc:
            embedding_ok = False
            embedding_warning = f"Cannot reach Ollama: {exc}"

    # Chat fallback chain — which generation providers are wired (no network call;
    # provider clients are constructed lazily).
    from ..ai import get_chat_client  # noqa: PLC0415
    from ..ai.providers import FallbackChatClient  # noqa: PLC0415

    chat_client = get_chat_client(config)
    if isinstance(chat_client, FallbackChatClient):
        chat_chain = [c.model_name for c in chat_client._clients]  # noqa: SLF001
    else:
        chat_chain = [chat_client.model_name]

    return jsonify({
        "library": {
            "metadataDbReadable": db_readable,
            "bookCount":          calibre_count,
            "indexedBookCount":   indexed_count,
            "pendingBookCount":   max(0, calibre_count - indexed_count),
            "statusBreakdown":    status_breakdown,
        },
        "embedding": {
            "provider": config.embedding_provider,
            "model":    embedding_model,
            "ok":       embedding_ok,
            "warning":  embedding_warning,
        },
        "chat": {
            "priority": config.chat_provider_priority,
            "chain":    chat_chain,
        },
        "lastIngestionRun": last_run,
    })
