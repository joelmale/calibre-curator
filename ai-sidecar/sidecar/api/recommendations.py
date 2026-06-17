from __future__ import annotations

from flask import Blueprint, jsonify

from ..security import require_bearer_token

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.route("/books/<int:book_id>")
@require_bearer_token
def book_recommendations(book_id: int):
    return jsonify({"error": "not_implemented", "detail": "Available in Phase 4"}), 501


@recommendations_bp.route("/user/<user_key>")
@require_bearer_token
def user_recommendations(user_key: str):
    return jsonify({"error": "not_implemented", "detail": "Available in Phase 4"}), 501
