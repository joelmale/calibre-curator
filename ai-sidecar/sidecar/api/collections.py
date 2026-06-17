from __future__ import annotations

from flask import Blueprint, jsonify

from ..security import require_bearer_token

collections_bp = Blueprint("collections", __name__)


@collections_bp.route("/")
@require_bearer_token
def list_collections():
    return jsonify({"collections": []}), 200


@collections_bp.route("/<collection_id>")
@require_bearer_token
def get_collection(collection_id: str):
    return jsonify({"error": "not_found", "detail": collection_id}), 404
