from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from ..config import get_config
from ..db.repositories import BookAiLookup, ChunkRepository
from ..db.session import get_db
from ..embeddings import get_embedding_provider
from ..security import require_bearer_token
from ..vectors import get_vector_store

recommendations_bp = Blueprint("recommendations", __name__)

_DEFAULT_LIMIT = 5
_MAX_LIMIT = 20


def _distance_to_percent(distance: float) -> int:
    return max(0, min(100, int((1.0 - distance / 2.0) * 100)))


def _format_rec(book_row, chunk_text: str, heading: str | None, distance: float) -> dict:
    return {
        "bookId":       int(book_row["calibre_book_id"]),
        "title":        book_row["title"],
        "authors":      json.loads(book_row["authors_json"] or "[]"),
        "matchPercent": _distance_to_percent(distance),
        "matchReasons": [heading] if heading else [chunk_text[:120]],
        "score":        round(1.0 - distance / 2.0, 4),
    }


@recommendations_bp.route("/books/<int:book_id>")
@require_bearer_token
def book_recommendations(book_id: int):
    limit = min(int(request.args.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)

    with get_db() as conn:
        chunks = ChunkRepository.get_book_chunks(conn, book_id)

    if not chunks:
        return jsonify({
            "error": "not_ready",
            "detail": "This book has not been indexed yet",
        }), 404

    config = get_config()
    try:
        provider = get_embedding_provider(config)
        store = get_vector_store(config, provider.model_name)

        # Use the first chunk as the query vector — representative of the book's opening
        query_text = chunks[0]["text"]
        query_vec = provider.embed([query_text])[0]
        raw = store.search(query_vec, n_results=limit * 3, exclude_book_id=book_id)
    except Exception as exc:
        return jsonify({"error": "search_failed", "detail": str(exc)}), 503

    # Deduplicate by book, keep best chunk per book
    seen: dict[int, tuple] = {}
    for r in raw:
        if r.calibre_book_id not in seen or r.distance < seen[r.calibre_book_id][0]:
            seen[r.calibre_book_id] = (r.distance, r.text, r.heading)

    top = sorted(seen.items(), key=lambda kv: kv[1][0])[:limit]

    with get_db() as conn:
        book_rows = BookAiLookup.get_by_ids(conn, [bid for bid, _ in top])

    recs = []
    for bid, (distance, text, heading) in top:
        if bid in book_rows:
            recs.append(_format_rec(book_rows[bid], text, heading, distance))

    return jsonify({"sourceBookId": book_id, "recommendations": recs})


@recommendations_bp.route("/user/<user_key>")
@require_bearer_token
def user_recommendations(user_key: str):
    # Phase 5: use recommendation_events table to build a personalised query vector.
    return jsonify({
        "error": "not_implemented",
        "detail": "User recommendations available in Phase 5",
    }), 501
