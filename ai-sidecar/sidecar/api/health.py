from __future__ import annotations

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

VERSION = "0.1.0"


@health_bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "version": VERSION})
