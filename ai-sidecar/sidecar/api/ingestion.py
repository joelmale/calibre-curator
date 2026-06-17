from __future__ import annotations

from flask import Blueprint, jsonify

from ..security import require_bearer_token

ingestion_bp = Blueprint("ingestion", __name__)


@ingestion_bp.route("/run", methods=["POST"])
@require_bearer_token
def trigger_run():
    return jsonify({"error": "not_implemented", "detail": "Available in Phase 2"}), 501


@ingestion_bp.route("/runs/latest")
@require_bearer_token
def latest_run():
    return jsonify({"runId": None, "status": "idle"}), 200
