from __future__ import annotations

import os

from flask import Flask

from .config import get_config
from .logging_config import configure_logging
from .db.schema import init_db
from .api.health import health_bp
from .api.status import status_bp
from .api.ingestion import ingestion_bp
from .api.search import search_bp
from .api.collections import collections_bp
from .api.recommendations import recommendations_bp
from .api.enrichment import enrichment_bp
from .api.duplicates import duplicates_bp
from .api.mood import mood_bp
from .api.sequences import sequences_bp
from .api.providers import providers_bp


def create_app() -> Flask:
    configure_logging()
    app = Flask(__name__)
    config = get_config()

    init_db(config.sidecar_db_path)

    # Load saved per-provider rate limits into the in-memory limiter.
    from .ai.rate_limiter import get_rate_limiter
    from .db.repositories import ProviderSettingsRepository
    from .db.session import get_db
    try:
        with get_db() as conn:
            get_rate_limiter().load(ProviderSettingsRepository.get_all(conn))
    except Exception:  # noqa: BLE001 — never block startup on settings load
        pass

    app.register_blueprint(health_bp)
    app.register_blueprint(status_bp, url_prefix="/api/v1")
    app.register_blueprint(ingestion_bp, url_prefix="/api/v1/ingestion")
    app.register_blueprint(search_bp, url_prefix="/api/v1/search")
    app.register_blueprint(collections_bp, url_prefix="/api/v1/collections")
    app.register_blueprint(recommendations_bp, url_prefix="/api/v1/recommendations")
    app.register_blueprint(enrichment_bp, url_prefix="/api/v1/enrichment")
    app.register_blueprint(duplicates_bp, url_prefix="/api/v1/duplicates")
    app.register_blueprint(mood_bp, url_prefix="/api/v1/mood")
    app.register_blueprint(sequences_bp, url_prefix="/api/v1/sequences")
    app.register_blueprint(providers_bp, url_prefix="/api/v1/providers")

    # Guard against Werkzeug reloader spawning two scheduler instances in dev
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" or config.app_env != "development":
        from .workers.scheduler import start_scheduler
        start_scheduler(config)

    return app
