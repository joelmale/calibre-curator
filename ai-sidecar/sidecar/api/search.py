from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from ..config import get_config
from ..db.repositories import BookAiLookup
from ..db.session import get_db
from ..embeddings import get_embedding_provider
from ..security import require_bearer_token
from ..vectors import get_vector_store
from ._coverage import get_index_coverage

search_bp = Blueprint("search", __name__)

_DEFAULT_LIMIT = 10
_MAX_LIMIT = 50


def _distance_to_percent(distance: float) -> int:
    """Convert cosine distance [0, 2] to match percent [0, 100]."""
    return max(0, min(100, int((1.0 - distance / 2.0) * 100)))


def _format_result(book_row, chunk_text: str, heading: str | None, distance: float) -> dict:
    return {
        "bookId":       int(book_row["calibre_book_id"]),
        "title":        book_row["title"],
        "authors":      json.loads(book_row["authors_json"] or "[]"),
        "matchPercent": _distance_to_percent(distance),
        "matchReasons": [heading] if heading else [chunk_text[:120]],
        "score":        round(1.0 - distance / 2.0, 4),
    }


@search_bp.route("/semantic", methods=["POST"])
@require_bearer_token
def semantic_search():
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "bad_request", "detail": "query is required"}), 400

    limit = min(int(body.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)

    config = get_config()
    try:
        provider = get_embedding_provider(config)
        store = get_vector_store(config, provider.model_name)
        query_vec = provider.embed_query([query])[0]
        # Fetch more than needed so we can deduplicate by book;
        # apply the relevance threshold so irrelevant results are dropped.
        raw = store.search(
            query_vec,
            n_results=limit * 3,
            max_distance=config.search_max_distance,
        )
    except Exception as exc:
        return jsonify({"error": "search_failed", "detail": str(exc)}), 503

    # Deduplicate: keep only the best chunk per book
    seen: dict[int, tuple] = {}
    for r in raw:
        if r.calibre_book_id not in seen or r.distance < seen[r.calibre_book_id][0]:
            seen[r.calibre_book_id] = (r.distance, r.text, r.heading)

    top = sorted(seen.items(), key=lambda kv: kv[1][0])[:limit]

    with get_db() as conn:
        book_rows = BookAiLookup.get_by_ids(conn, [bid for bid, _ in top])

    results = []
    for book_id, (distance, text, heading) in top:
        if book_id in book_rows:
            results.append(_format_result(book_rows[book_id], text, heading, distance))

    coverage = get_index_coverage(config)
    return jsonify({"query": query, "results": results, "indexCoverage": coverage})
