from __future__ import annotations

import threading

from flask import Blueprint, jsonify, request

from ..db.repositories import IngestionRunRepository
from ..db.session import get_db
from ..ingestion.pipeline import get_progress, is_running, run_pipeline_once
from ..security import require_bearer_token

ingestion_bp = Blueprint("ingestion", __name__)


@ingestion_bp.route("/run", methods=["POST"])
@require_bearer_token
def trigger_run():
    if is_running():
        return jsonify({
            "error": "already_running",
            "detail": "An ingestion run is already in progress",
        }), 409

    body = request.get_json(silent=True) or {}
    raw_limit = body.get("limit")
    limit: int | None = None
    if raw_limit is not None:
        try:
            limit = max(1, int(raw_limit))
        except (TypeError, ValueError):
            pass

    with get_db() as conn:
        run_id = IngestionRunRepository.start(conn)

    def _run() -> None:
        run_pipeline_once(run_id=run_id, limit=limit)

    thread = threading.Thread(
        target=_run,
        daemon=True,
        name=f"ingestion-run-{run_id}",
    )
    thread.start()

    return jsonify({"runId": run_id, "status": "queued", "limit": limit}), 202


@ingestion_bp.route("/runs/latest")
@require_bearer_token
def latest_run():
    with get_db() as conn:
        run = IngestionRunRepository.get_latest(conn)
    return jsonify(run if run else {"runId": None, "status": "idle"}), 200


@ingestion_bp.route("/progress")
@require_bearer_token
def ingestion_progress():
    """Return live in-run progress (or {phase:'idle'} when nothing is running).

    The data is sourced from the in-memory progress object updated by the
    pipeline thread — no DB reads, no added latency.
    """
    return jsonify(get_progress()), 200
