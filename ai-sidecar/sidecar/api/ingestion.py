from __future__ import annotations

import threading

from flask import Blueprint, jsonify, request

from ..db.repositories import IngestionRunRepository
from ..db.session import get_db
from ..ingestion.pipeline import is_running, run_pipeline_once
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

    # Create the DB row before spawning so we can return its ID immediately
    with get_db() as conn:
        run_id = IngestionRunRepository.start(conn)

    def _run() -> None:
        run_pipeline_once(run_id=run_id)

    thread = threading.Thread(
        target=_run,
        daemon=True,
        name=f"ingestion-run-{run_id}",
    )
    thread.start()

    return jsonify({"runId": run_id, "status": "queued"}), 202


@ingestion_bp.route("/runs/latest")
@require_bearer_token
def latest_run():
    with get_db() as conn:
        run = IngestionRunRepository.get_latest(conn)
    return jsonify(run if run else {"runId": None, "status": "idle"}), 200
