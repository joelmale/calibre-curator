from __future__ import annotations

import hashlib
import hmac
import os

import requests
from flask import Blueprint, Response, abort, jsonify, request
from .usermanagement import user_login_required
from .render_template import render_title_template

ai_bridge = Blueprint("ai_bridge", __name__, url_prefix="/ai")

SIDECAR_BASE_URL = os.getenv("AI_SIDECAR_BASE_URL", "http://ai-sidecar:8090").rstrip("/")
SIDECAR_TOKEN = os.getenv("AI_SIDECAR_SHARED_TOKEN", "")
SIDECAR_ENABLED = os.getenv("AI_SIDECAR_ENABLED", "false").lower() == "true"

ALLOWED_METHODS = {"GET", "POST"}


def _sidecar_headers() -> dict[str, str]:
    if not SIDECAR_TOKEN:
        abort(503)
    return {
        "Authorization": f"Bearer {SIDECAR_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _pseudonymous_user_key(user_id: int) -> str:
    """HMAC-SHA256 of the Calibre-Web user ID keyed by the shared token.
    Stable per user; the raw user ID never leaves the proxy."""
    return hmac.new(
        SIDECAR_TOKEN.encode("utf-8"),
        f"calibre-user:{user_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@ai_bridge.route("/", methods=["GET"])
@user_login_required
def dashboard() -> str:
    if not SIDECAR_ENABLED:
        abort(404)
    return render_title_template(
        "ai_dashboard.html",
        title="AI Curated Library",
        page="ai-dashboard",
    )


@ai_bridge.route("/api/<path:subpath>", methods=["GET", "POST"])
@user_login_required
def proxy_api(subpath: str) -> Response:
    if not SIDECAR_ENABLED:
        abort(404)
    if request.method not in ALLOWED_METHODS:
        abort(405)

    url = f"{SIDECAR_BASE_URL}/api/v1/{subpath}"

    try:
        sidecar_response = requests.request(
            method=request.method,
            url=url,
            headers=_sidecar_headers(),
            params=request.args,
            json=request.get_json(silent=True),
            timeout=30,
        )
    except requests.RequestException as exc:
        return jsonify({"error": "sidecar_unavailable", "detail": str(exc)}), 503

    return Response(
        response=sidecar_response.content,
        status=sidecar_response.status_code,
        content_type=sidecar_response.headers.get("Content-Type", "application/json"),
    )
