from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ..ai import configured_providers
from ..ai.rate_limiter import get_rate_limiter
from ..config import get_config
from ..db.repositories import ProviderSettingsRepository
from ..db.session import get_db
from ..security import require_bearer_token

logger = logging.getLogger(__name__)

providers_bp = Blueprint("providers", __name__)


def _coerce_limit(value) -> int | None:
    """Empty / 0 / null => unlimited (None); otherwise a positive int."""
    if value in (None, "", "0", 0):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


@providers_bp.route("", methods=["GET"])
@providers_bp.route("/", methods=["GET"])
@require_bearer_token
def list_providers():
    config = get_config()
    limiter = get_rate_limiter()
    out = []
    for spec in configured_providers(config):
        name = spec["provider"]
        limit = limiter.get_limit(name)
        out.append({
            "provider":  name,
            "model":     spec["model"],
            "available": spec["available"],
            "enabled":   limit.enabled,
            "rpm":       limit.rpm,
            "rph":       limit.rph,
            "usage":     limiter.usage(name),
            "local":     name == "ollama",
        })
    return jsonify({"providers": out})


@providers_bp.route("/limits", methods=["POST"])
@require_bearer_token
def set_limits():
    body = request.get_json(silent=True) or {}
    provider = str(body.get("provider", "")).strip().lower()
    if not provider:
        return jsonify({"error": "bad_request", "detail": "provider is required"}), 400

    rpm = _coerce_limit(body.get("rpm"))
    rph = _coerce_limit(body.get("rph"))
    enabled = bool(body.get("enabled", True))

    with get_db() as conn:
        ProviderSettingsRepository.upsert(conn, provider, rpm, rph, enabled)
    get_rate_limiter().set_limit(provider, rpm, rph, enabled)

    logger.info(
        "Provider '%s' limits updated: rpm=%s rph=%s enabled=%s",
        provider, rpm, rph, enabled,
    )
    return jsonify({"ok": True, "provider": provider, "rpm": rpm, "rph": rph, "enabled": enabled})
