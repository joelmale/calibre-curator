from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, request

from ..config import get_config
from ..db.session import get_db
from ..embeddings import get_embedding_provider
from ..security import require_bearer_token
from ..vectors import get_vector_store

logger = logging.getLogger(__name__)

duplicates_bp = Blueprint("duplicates", __name__)

# similarity > 0.92  ⇒  cosine distance < 0.08
_NEAR_DISTANCE = 0.08
_DEFAULT_SCAN = 300
_MAX_SCAN = 2000


def _formats_for(conn, book_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT format FROM book_formats_ai WHERE calibre_book_id = ? ORDER BY format",
        (book_id,),
    ).fetchall()
    return [r["format"] for r in rows]


def _book_brief(conn, book_id: int) -> dict:
    row = conn.execute(
        "SELECT calibre_book_id, title, author_sort, authors_json FROM books_ai "
        "WHERE calibre_book_id = ?",
        (book_id,),
    ).fetchone()
    if row is None:
        return {"bookId": book_id, "title": "(unknown)", "authors": [], "formats": []}
    return {
        "bookId": int(row["calibre_book_id"]),
        "title": row["title"],
        "authorSort": row["author_sort"] or "",
        "authors": json.loads(row["authors_json"] or "[]"),
        "formats": _formats_for(conn, book_id),
    }


@duplicates_bp.route("/exact", methods=["GET"])
@require_bearer_token
def exact():
    """Books sharing a case-insensitive (title, author_sort) — likely true dupes."""
    with get_db() as conn:
        groups = conn.execute(
            """
            SELECT GROUP_CONCAT(calibre_book_id) AS ids, COUNT(*) AS n,
                   title, author_sort
            FROM books_ai
            GROUP BY LOWER(title), LOWER(COALESCE(author_sort, ''))
            HAVING n > 1
            ORDER BY n DESC, title ASC
            """
        ).fetchall()

        result = []
        for g in groups:
            ids = [int(x) for x in g["ids"].split(",")]
            result.append({
                "key": f"{g['title']} — {g['author_sort'] or ''}",
                "count": int(g["n"]),
                "books": [_book_brief(conn, bid) for bid in ids],
            })

    return jsonify({"groups": result, "groupCount": len(result)})


@duplicates_bp.route("/semantic", methods=["GET"])
@require_bearer_token
def semantic():
    """Near-duplicate detection: books whose text is >92% similar (same work,
    different edition/title). Bounded scan over the first `scan` indexed books."""
    scan = min(int(request.args.get("scan", _DEFAULT_SCAN)), _MAX_SCAN)
    config = get_config()

    try:
        provider = get_embedding_provider(config)
        store = get_vector_store(config, provider.model_name)
    except Exception as exc:
        return jsonify({"error": "vector_unavailable", "detail": str(exc)}), 503

    with get_db() as conn:
        rows = conn.execute(
            "SELECT calibre_book_id FROM books_ai "
            "WHERE ingestion_status = 'indexed' ORDER BY calibre_book_id ASC LIMIT ?",
            (scan,),
        ).fetchall()
        book_ids = [int(r["calibre_book_id"]) for r in rows]

        seen_pairs: set[tuple[int, int]] = set()
        pairs = []
        for bid in book_ids:
            vec = store.get_book_embedding(bid)
            if vec is None:
                continue
            neighbours = store.search(vec, n_results=4, exclude_book_id=bid)
            for n in neighbours:
                if n.distance > _NEAR_DISTANCE:
                    continue
                pair_key = (min(bid, n.calibre_book_id), max(bid, n.calibre_book_id))
                if pair_key in seen_pairs or pair_key[0] == pair_key[1]:
                    continue
                seen_pairs.add(pair_key)
                similarity = round(1.0 - n.distance, 4)
                pairs.append({
                    "similarity": similarity,
                    "books": [_book_brief(conn, pair_key[0]), _book_brief(conn, pair_key[1])],
                })

    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    return jsonify({"scanned": len(book_ids), "pairs": pairs, "pairCount": len(pairs)})
