from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import Config

_scheduler: BackgroundScheduler | None = None


def start_scheduler(config: Config) -> None:
    global _scheduler
    if _scheduler is not None:
        return

    from ..ingestion.pipeline import run_pipeline_once

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_pipeline_once,
        trigger="interval",
        seconds=config.scan_interval_seconds,
        id="ingestion_scanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
