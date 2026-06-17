from __future__ import annotations

import hmac
from functools import wraps

from flask import jsonify, request

from .config import get_config


def require_bearer_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        config = get_config()
        if not config.shared_token:
            return jsonify({"error": "server_misconfigured", "detail": "No shared token configured"}), 503

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "unauthorized", "detail": "Bearer token required"}), 401

        token = auth[len("Bearer "):]
        if not hmac.compare_digest(token.encode("utf-8"), config.shared_token.encode("utf-8")):
            return jsonify({"error": "unauthorized", "detail": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated
