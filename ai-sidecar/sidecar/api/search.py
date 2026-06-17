from __future__ import annotations

from flask import Blueprint, jsonify

from ..security import require_bearer_token

search_bp = Blueprint("search", __name__)


@search_bp.route("/semantic", methods=["POST"])
@require_bearer_token
def semantic_search():
    return jsonify({"error": "not_implemented", "detail": "Available in Phase 4"}), 501
