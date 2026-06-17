from __future__ import annotations

import os

from flask import Flask

from .config import get_config
from .db.schema import init_db
from .api.health import health_bp
from .api.status import status_bp
from .api.ingestion import ingestion_bp
from .api.search import search_bp
from .api.collections import collections_bp
from .api.recommendations import recommendations_bp


def create_app() -> Flask:
    app = Flask(__name__)
    config = get_config()

    init_db(config.sidecar_db_path)

    app.register_blueprint(health_bp)
    app.register_blueprint(status_bp, url_prefix="/api/v1")
    app.register_blueprint(ingestion_bp, url_prefix="/api/v1/ingestion")
    app.register_blueprint(search_bp, url_prefix="/api/v1/search")
    app.register_blueprint(collections_bp, url_prefix="/api/v1/collections")
    app.register_blueprint(recommendations_bp, url_prefix="/api/v1/recommendations")

    # Guard against Werkzeug reloader spawning two scheduler instances in dev
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" or config.app_env != "development":
        from .workers.scheduler import start_scheduler
        start_scheduler(config)

    return app
