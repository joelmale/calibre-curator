from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class ProviderLimit:
    rpm: int | None = None   # max requests per rolling 60s (None = unlimited)
    rph: int | None = None   # max requests per rolling 3600s (None = unlimited)
    enabled: bool = True     # False = never use this provider


class RateLimiter:
    """Process-global per-provider rolling-window rate limiter.

    The sidecar runs a single gunicorn worker, so in-process state is consistent
    across the API threads and the background enrichment worker. Request
    timestamps live in memory (reset on restart — conservative); the configured
    limits are loaded from the DB so they survive restarts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._limits: dict[str, ProviderLimit] = {}
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def set_limit(
        self, provider: str, rpm: int | None, rph: int | None, enabled: bool = True
    ) -> None:
        with self._lock:
            self._limits[provider] = ProviderLimit(rpm, rph, enabled)

    def load(self, rows) -> None:
        """Bulk-load limits from DB rows (provider, rpm, rph, enabled)."""
        with self._lock:
            for r in rows:
                self._limits[r["provider"]] = ProviderLimit(
                    r["rpm"], r["rph"], bool(r["enabled"])
                )

    def get_limit(self, provider: str) -> ProviderLimit:
        with self._lock:
            return self._limits.get(provider, ProviderLimit())

    @staticmethod
    def _purge(dq: deque[float], now: float) -> None:
        while dq and now - dq[0] > 3600:
            dq.popleft()

    def allow(self, provider: str) -> bool:
        """Return True and record a request if the provider is under its limits.

        Returns False if the provider is disabled or either window is full —
        callers should treat that as "skip this provider".
        """
        now = time.monotonic()
        with self._lock:
            cfg = self._limits.get(provider, ProviderLimit())
            if not cfg.enabled:
                return False
            dq = self._events[provider]
            self._purge(dq, now)
            if cfg.rpm is not None:
                minute = sum(1 for t in dq if now - t <= 60)
                if minute >= cfg.rpm:
                    return False
            if cfg.rph is not None and len(dq) >= cfg.rph:
                return False
            dq.append(now)
            return True

    def usage(self, provider: str) -> dict[str, int]:
        now = time.monotonic()
        with self._lock:
            dq = self._events.get(provider, deque())
            self._purge(dq, now)
            minute = sum(1 for t in dq if now - t <= 60)
            return {"lastMinute": minute, "lastHour": len(dq)}


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
