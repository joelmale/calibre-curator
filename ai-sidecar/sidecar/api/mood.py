from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, request

from ..ai import ChatError, get_chat_client
from ..config import get_config
from ..db.repositories import BookAiLookup
from ..db.session import get_db
from ..embeddings import get_embedding_provider
from ..security import require_bearer_token
from ..vectors import get_vector_store
from ._coverage import get_index_coverage

logger = logging.getLogger(__name__)

mood_bp = Blueprint("mood", __name__)

_DEFAULT_LIMIT = 12
_MAX_LIMIT = 30

_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "semanticQuery": {"type": "string"},
        "filters": {
            "type": "object",
            "properties": {
                "excludeTags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "explanation": {"type": "string"},
    },
    "required": ["semanticQuery", "explanation"],
}

_SYSTEM_PROMPT = (
    "You are a reading-recommendation assistant. The user describes a mood or "
    "the kind of book they want in free text. Translate it into a search spec. "
    "Return ONLY JSON. 'semanticQuery' is a concise phrase capturing themes, tone "
    "and genre to search a vector index of books. 'filters.excludeTags' lists "
    "lowercase tags to avoid if the user excluded something. 'explanation' is one "
    "friendly sentence telling the user what you searched for and why."
)


def _distance_to_percent(distance: float) -> int:
    return max(0, min(100, int((1.0 - distance / 2.0) * 100)))


@mood_bp.route("/search", methods=["POST"])
@require_bearer_token
def mood_search():
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "bad_request", "detail": "prompt is required"}), 400
    limit = min(int(body.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)

    config = get_config()
    chat = get_chat_client(config)

    # 1. LLM extracts a structured search intent from the free-text mood.
    try:
        intent = chat.chat_json(_SYSTEM_PROMPT, prompt, schema=_INTENT_SCHEMA)
    except ChatError as exc:
        return jsonify({"error": "chat_unavailable", "detail": str(exc)}), 503

    semantic_query = str(intent.get("semanticQuery") or prompt).strip()
    explanation = str(intent.get("explanation") or "").strip()
    filters = intent.get("filters") or {}
    exclude_tags = {
        str(t).strip().lower()
        for t in (filters.get("excludeTags") or [])
        if str(t).strip()
    }

    # 2. Vector search on the derived query.
    try:
        provider = get_embedding_provider(config)
        store = get_vector_store(config, provider.model_name)
        query_vec = provider.embed_query([semantic_query])[0]
        # Apply the relevance threshold: results further than max_distance are dropped.
        raw = store.search(
            query_vec,
            n_results=limit * 4,
            max_distance=config.search_max_distance,
        )
    except Exception as exc:
        return jsonify({"error": "search_failed", "detail": str(exc)}), 503

    # Best chunk per book.
    best: dict[int, tuple] = {}
    for r in raw:
        if r.calibre_book_id not in best or r.distance < best[r.calibre_book_id][0]:
            best[r.calibre_book_id] = (r.distance, r.text, r.heading)

    ordered = sorted(best.items(), key=lambda kv: kv[1][0])

    with get_db() as conn:
        rows = BookAiLookup.get_by_ids(conn, [bid for bid, _ in ordered])

    # 3. Apply tag-exclusion filter and shape results.
    results = []
    for book_id, (distance, text, heading) in ordered:
        row = rows.get(book_id)
        if row is None:
            continue
        tags = {t.lower() for t in json.loads(row["tags_json"] or "[]")}
        if exclude_tags and tags & exclude_tags:
            continue
        results.append({
            "bookId": book_id,
            "title": row["title"],
            "authors": json.loads(row["authors_json"] or "[]"),
            "matchPercent": _distance_to_percent(distance),
            "matchReasons": [heading] if heading else [text[:120]],
            "score": round(1.0 - distance / 2.0, 4),
        })
        if len(results) >= limit:
            break

    # 4. Honest no-match: when no results pass the threshold, replace the upbeat
    #    LLM explanation with a factual message so the frontend doesn't present
    #    irrelevant books as confident matches.
    if not results:
        explanation = (
            f"I couldn't find a good match for '{semantic_query}' in your library yet."
        )

    coverage = get_index_coverage(config)
    return jsonify({
        "prompt": prompt,
        "semanticQuery": semantic_query,
        "explanation": explanation,
        "excludedTags": sorted(exclude_tags),
        "results": results,
        "indexCoverage": coverage,
    })
