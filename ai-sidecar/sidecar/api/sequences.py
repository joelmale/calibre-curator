from __future__ import annotations

import json
import logging
import re

from flask import Blueprint, jsonify, request

from ..ai import ChatError, get_chat_client
from ..config import get_config
from ..db.repositories import BookAiLookup, CollectionRepository
from ..db.session import get_db
from ..embeddings import get_embedding_provider
from ..security import require_bearer_token
from ..vectors import get_vector_store

logger = logging.getLogger(__name__)

sequences_bp = Blueprint("sequences", __name__)

_CANDIDATE_POOL = 30
_MAX_STEPS = 12

_SEQUENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "bookId": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["bookId", "reason"],
            },
        },
    },
    "required": ["explanation", "steps"],
}

_SYSTEM_PROMPT = (
    "You are a reading-curriculum designer. Given a learning/reading goal and a "
    "numbered list of candidate books (with ids, titles, authors, tags), select "
    "and ORDER a coherent reading sequence of 5-12 books that builds the reader "
    "from foundational to advanced. Use ONLY books from the candidate list, "
    "referencing them by their exact bookId. Return ONLY JSON: 'steps' is the "
    "ordered list (each with bookId and a one-sentence reason for its position), "
    "and 'explanation' is a short overview of the arc."
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "sequence")[:60]


def _candidate_line(idx: int, row) -> str:
    authors = ", ".join(json.loads(row["authors_json"] or "[]")) or (row["author_sort"] or "")
    return f'{idx}. bookId={row["calibre_book_id"]} "{row["title"]}" by {authors}'


@sequences_bp.route("/generate", methods=["POST"])
@require_bearer_token
def generate():
    body = request.get_json(silent=True) or {}
    goal = (body.get("goal") or "").strip()
    seed_book_id = body.get("seedBookId")
    if not goal and seed_book_id is None:
        return jsonify({"error": "bad_request", "detail": "goal or seedBookId is required"}), 400

    config = get_config()
    chat = get_chat_client(config)

    # Pass 1 — narrow the library to a candidate pool via semantic search.
    try:
        provider = get_embedding_provider(config)
        store = get_vector_store(config, provider.model_name)
    except Exception as exc:
        return jsonify({"error": "vector_unavailable", "detail": str(exc)}), 503

    query_text = goal
    with get_db() as conn:
        if seed_book_id is not None:
            seed = conn.execute(
                "SELECT title FROM books_ai WHERE calibre_book_id = ?",
                (int(seed_book_id),),
            ).fetchone()
            if seed and not query_text:
                query_text = f"books similar to and building on {seed['title']}"
            elif seed:
                query_text = f"{goal} (seed: {seed['title']})"

    try:
        query_vec = provider.embed([query_text])[0]
        raw = store.search(query_vec, n_results=_CANDIDATE_POOL * 3)
    except Exception as exc:
        return jsonify({"error": "search_failed", "detail": str(exc)}), 503

    best: dict[int, float] = {}
    for r in raw:
        if r.calibre_book_id not in best or r.distance < best[r.calibre_book_id]:
            best[r.calibre_book_id] = r.distance
    candidate_ids = [bid for bid, _ in sorted(best.items(), key=lambda kv: kv[1])][:_CANDIDATE_POOL]

    if not candidate_ids:
        return jsonify({"error": "no_candidates", "detail": "No indexed books matched the goal"}), 404

    with get_db() as conn:
        rows = BookAiLookup.get_by_ids(conn, candidate_ids)

    # Preserve semantic ranking order in the candidate list shown to the model.
    ordered_rows = [rows[bid] for bid in candidate_ids if bid in rows]
    candidate_text = "\n".join(
        _candidate_line(i, row) for i, row in enumerate(ordered_rows, 1)
    )

    # Pass 2 — LLM orders a subset into a sequence.
    user_prompt = (
        f"Goal: {goal or '(similar to seed book)'}\n\n"
        f"Candidate books:\n{candidate_text}\n\n"
        "Produce the ordered reading sequence JSON now."
    )
    try:
        result = chat.chat_json(_SYSTEM_PROMPT, user_prompt, schema=_SEQUENCE_SCHEMA)
    except ChatError as exc:
        return jsonify({"error": "chat_unavailable", "detail": str(exc)}), 503

    valid_ids = set(candidate_ids)
    steps = []
    rank = 1
    for step in result.get("steps", []):
        try:
            bid = int(step.get("bookId"))
        except (TypeError, ValueError):
            continue
        if bid not in valid_ids or bid not in rows:
            continue  # model hallucinated an id — drop it
        row = rows[bid]
        steps.append({
            "rank": rank,
            "bookId": bid,
            "title": row["title"],
            "authors": json.loads(row["authors_json"] or "[]"),
            "reason": str(step.get("reason") or "").strip(),
        })
        rank += 1
        if rank > _MAX_STEPS:
            break

    return jsonify({
        "goal": goal,
        "explanation": str(result.get("explanation") or "").strip(),
        "candidateCount": len(candidate_ids),
        "steps": steps,
    })


@sequences_bp.route("/save", methods=["POST"])
@require_bearer_token
def save():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    goal = (body.get("goal") or "").strip()
    steps = body.get("steps") or []
    if not title:
        return jsonify({"error": "bad_request", "detail": "title is required"}), 400
    if not isinstance(steps, list) or not steps:
        return jsonify({"error": "bad_request", "detail": "steps are required"}), 400

    items: list[tuple[int, int, float, str]] = []
    for i, step in enumerate(steps, 1):
        try:
            bid = int(step["bookId"])
        except (KeyError, TypeError, ValueError):
            continue
        rank = int(step.get("rank", i))
        items.append((bid, rank, 1.0, str(step.get("reason") or "")))

    if not items:
        return jsonify({"error": "bad_request", "detail": "no valid steps"}), 400

    slug = _slugify(title)
    with get_db() as conn:
        CollectionRepository.save(
            conn,
            collection_slug=slug,
            title=title,
            description=goal or f"Reading sequence: {title}",
            collection_type="sequence",
            generation_prompt=goal,
            items=items,
        )
    return jsonify({"ok": True, "collectionSlug": slug, "itemCount": len(items)}), 201


@sequences_bp.route("", methods=["GET"])
@sequences_bp.route("/", methods=["GET"])
@require_bearer_token
def list_sequences():
    with get_db() as conn:
        rows = CollectionRepository.list_by_type(conn, "sequence")
        out = []
        for r in rows:
            items = CollectionRepository.get_items(conn, r["collection_slug"])
            out.append({
                "collectionSlug": r["collection_slug"],
                "title": r["title"],
                "description": r["description"],
                "itemCount": int(r["item_count"]),
                "steps": [
                    {
                        "rank": int(it["rank"]),
                        "bookId": int(it["calibre_book_id"]),
                        "title": it["title"],
                        "authors": json.loads(it["authors_json"] or "[]") if it["authors_json"] else [],
                        "reason": it["match_reason"],
                    }
                    for it in items
                ],
            })
    return jsonify({"sequences": out})
