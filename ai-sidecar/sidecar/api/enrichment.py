from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, request

from ..ai import ChatError, get_chat_client
from ..config import get_config
from ..db.repositories import EnrichmentRepository
from ..db.session import get_db
from ..security import require_bearer_token

logger = logging.getLogger(__name__)

enrichment_bp = Blueprint("enrichment", __name__)

# How much of the book's text to feed the model as context.
_CONTEXT_CHARS = 8000
_MAX_BATCH = 100

_SUGGESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "readingLevel": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["tags", "description", "readingLevel", "confidence"],
}

_SYSTEM_PROMPT = (
    "You are a professional librarian creating catalogue metadata. "
    "Given a book's title, author, and an excerpt of its text, produce concise, "
    "accurate metadata. Return ONLY JSON matching the requested schema. "
    "Tags must be 3-8 lowercase subject keywords (genres, themes, topics, period). "
    "The description is a single neutral paragraph (40-80 words), no spoilers, no "
    "marketing language. readingLevel is one of: children, middle-grade, "
    "young-adult, general-adult, academic. confidence is 0.0-1.0 reflecting how "
    "sure you are given the excerpt."
)


def _build_user_prompt(title: str, author: str, text: str) -> str:
    return (
        f"Title: {title}\n"
        f"Author: {author or 'Unknown'}\n\n"
        f"Excerpt:\n{text}\n\n"
        "Produce the metadata JSON now."
    )


def _coerce_suggestion(raw: dict) -> dict:
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip().lower() for t in tags if str(t).strip()][:8]

    description = raw.get("description")
    description = str(description).strip() if description else None

    reading_level = raw.get("readingLevel")
    reading_level = str(reading_level).strip() if reading_level else None

    try:
        confidence = float(raw.get("confidence"))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = None

    return {
        "tags": tags,
        "description": description,
        "readingLevel": reading_level,
        "confidence": confidence,
    }


def _generate_for_book(conn, config, chat, calibre_book_id: int) -> dict:
    """Run the LLM for one book, persist the suggestion, return it. Raises on error."""
    book = conn.execute(
        "SELECT calibre_book_id, title, author_sort FROM books_ai WHERE calibre_book_id = ?",
        (calibre_book_id,),
    ).fetchone()
    if book is None:
        raise ValueError(f"book {calibre_book_id} not found")

    text = EnrichmentRepository.get_book_text(conn, calibre_book_id, _CONTEXT_CHARS)
    if not text.strip():
        raise ValueError("no extracted text available for this book")

    raw = chat.chat_json(
        _SYSTEM_PROMPT,
        _build_user_prompt(book["title"], book["author_sort"] or "", text),
        schema=_SUGGESTION_SCHEMA,
    )
    suggestion = _coerce_suggestion(raw)

    EnrichmentRepository.upsert_suggestion(
        conn,
        calibre_book_id=calibre_book_id,
        tags=suggestion["tags"],
        description=suggestion["description"],
        reading_level=suggestion["readingLevel"],
        confidence=suggestion["confidence"],
        chat_model=chat.model_name,
    )
    return {
        "bookId": calibre_book_id,
        "title": book["title"],
        "authorSort": book["author_sort"] or "",
        **suggestion,
        "chatModel": chat.model_name,
    }


@enrichment_bp.route("/queue", methods=["GET"])
@require_bearer_token
def get_queue():
    limit = min(int(request.args.get("limit", 50)), 200)
    with get_db() as conn:
        rows = EnrichmentRepository.get_candidates(conn, limit)
        total = EnrichmentRepository.count_candidates(conn)
    return jsonify({
        "totalCandidates": total,
        "books": [
            {
                "bookId": int(r["calibre_book_id"]),
                "title": r["title"],
                "authorSort": r["author_sort"] or "",
                "currentTags": json.loads(r["tags_json"] or "[]"),
            }
            for r in rows
        ],
    })


@enrichment_bp.route("/generate/<int:book_id>", methods=["POST"])
@require_bearer_token
def generate(book_id: int):
    config = get_config()
    chat = get_chat_client(config)
    try:
        with get_db() as conn:
            result = _generate_for_book(conn, config, chat, book_id)
    except ChatError as exc:
        return jsonify({"error": "chat_unavailable", "detail": str(exc)}), 503
    except ValueError as exc:
        return jsonify({"error": "bad_request", "detail": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        logger.exception("Enrichment generation failed for book %d", book_id)
        return jsonify({"error": "generation_failed", "detail": str(exc)}), 500
    return jsonify(result)


@enrichment_bp.route("/queue/batch", methods=["POST"])
@require_bearer_token
def queue_batch():
    body = request.get_json(silent=True) or {}
    count = min(max(1, int(body.get("count", 20))), _MAX_BATCH)
    with get_db() as conn:
        candidates = EnrichmentRepository.get_candidates(conn, count)
        ids = [int(r["calibre_book_id"]) for r in candidates]
        queued = EnrichmentRepository.enqueue(conn, ids)
    # Kick the background worker so the queue starts draining immediately.
    from ..workers.enrichment_worker import trigger_enrichment_drain
    trigger_enrichment_drain()
    return jsonify({"queued": queued, "bookIds": ids}), 202


@enrichment_bp.route("/suggestions", methods=["GET"])
@require_bearer_token
def suggestions():
    limit = min(int(request.args.get("limit", 100)), 500)
    with get_db() as conn:
        rows = EnrichmentRepository.get_pending_suggestions(conn, limit)
    return jsonify({
        "suggestions": [
            {
                "bookId": int(r["calibre_book_id"]),
                "title": r["title"],
                "authorSort": r["author_sort"] or "",
                "currentTags": json.loads(r["current_tags_json"] or "[]"),
                "suggestedTags": json.loads(r["suggested_tags_json"] or "[]"),
                "suggestedDescription": r["suggested_description"],
                "suggestedReadingLevel": r["suggested_reading_level"],
                "confidence": r["confidence"],
                "chatModel": r["chat_model"],
                "generatedAt": r["generated_at"],
            }
            for r in rows
        ],
    })


@enrichment_bp.route("/review", methods=["POST"])
@require_bearer_token
def review():
    """Record the outcome of an admin review + write-back.

    Called by the calibre-web bridge *after* it runs calibredb set_metadata, so
    the sidecar keeps the audit log and marks the suggestion reviewed. The
    sidecar never writes to the Calibre library itself.
    """
    body = request.get_json(silent=True) or {}
    try:
        book_id = int(body["bookId"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "bad_request", "detail": "bookId is required"}), 400

    applied_tags = body.get("appliedTags")
    if applied_tags is not None and not isinstance(applied_tags, list):
        return jsonify({"error": "bad_request", "detail": "appliedTags must be a list"}), 400

    with get_db() as conn:
        EnrichmentRepository.insert_review(
            conn,
            calibre_book_id=book_id,
            applied_tags=applied_tags,
            applied_description=body.get("appliedDescription"),
            applied_reading_level=body.get("appliedReadingLevel"),
            decision=body.get("decision") or {},
            writeback_status=body.get("writebackStatus", "applied"),
            writeback_error=body.get("writebackError"),
            reviewer=str(body.get("reviewer", "admin")),
        )
        EnrichmentRepository.mark_suggestion_reviewed(conn, book_id, "reviewed")
    return jsonify({"ok": True, "bookId": book_id})


@enrichment_bp.route("/dismiss/<int:book_id>", methods=["POST"])
@require_bearer_token
def dismiss(book_id: int):
    with get_db() as conn:
        EnrichmentRepository.mark_suggestion_reviewed(conn, book_id, "dismissed")
    return jsonify({"ok": True, "bookId": book_id})


@enrichment_bp.route("/reviews", methods=["GET"])
@require_bearer_token
def reviews():
    limit = min(int(request.args.get("limit", 100)), 500)
    with get_db() as conn:
        rows = EnrichmentRepository.get_reviews(conn, limit)
    return jsonify({
        "reviews": [
            {
                "bookId": int(r["calibre_book_id"]),
                "title": r["title"],
                "authorSort": r["author_sort"] or "",
                "appliedTags": json.loads(r["applied_tags_json"]) if r["applied_tags_json"] else None,
                "appliedDescription": r["applied_description"],
                "appliedReadingLevel": r["applied_reading_level"],
                "writebackStatus": r["writeback_status"],
                "writebackError": r["writeback_error"],
                "reviewer": r["reviewer"],
                "appliedAt": r["applied_at"],
            }
            for r in rows
        ],
    })
