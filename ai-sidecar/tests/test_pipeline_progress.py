"""Unit tests for the pipeline in-memory progress object.

Verifies that get_progress() returns the idle sentinel before a run,
that _set_progress() updates individual fields without clearing others,
and that _reset_progress() restores the idle state.
"""
from __future__ import annotations

import pytest

from sidecar.ingestion.pipeline import (
    _reset_progress,
    _set_progress,
    get_progress,
)


class TestProgressObject:
    def setup_method(self):
        """Ensure clean idle state before each test."""
        _reset_progress()

    def teardown_method(self):
        """Restore idle state after each test."""
        _reset_progress()

    def test_idle_by_default(self):
        p = get_progress()
        assert p["phase"] == "idle"
        assert p["current_book_id"] is None
        assert p["current_title"] is None
        assert p["total_to_process"] == 0
        assert p["current_index"] == 0

    def test_set_progress_partial_update(self):
        _set_progress(phase="scanning")
        p = get_progress()
        assert p["phase"] == "scanning"
        # Other fields unchanged
        assert p["total_to_process"] == 0
        assert p["current_book_id"] is None

    def test_set_progress_extracting(self):
        _set_progress(
            phase="extracting",
            total_to_process=50,
            current_index=3,
            current_book_id=42,
            current_title="Dune",
        )
        p = get_progress()
        assert p["phase"] == "extracting"
        assert p["total_to_process"] == 50
        assert p["current_index"] == 3
        assert p["current_book_id"] == 42
        assert p["current_title"] == "Dune"

    def test_set_progress_embedding(self):
        _set_progress(phase="embedding", chunks_total=200, chunks_embedded_so_far=64)
        p = get_progress()
        assert p["phase"] == "embedding"
        assert p["chunks_total"] == 200
        assert p["chunks_embedded_so_far"] == 64

    def test_reset_progress_restores_idle(self):
        _set_progress(phase="embedding", current_title="Foundation", current_book_id=7)
        _reset_progress()
        p = get_progress()
        assert p["phase"] == "idle"
        assert p["current_title"] is None
        assert p["current_book_id"] is None

    def test_get_progress_returns_copy(self):
        """Mutating the returned dict must not affect the internal state."""
        p1 = get_progress()
        p1["phase"] = "hacked"
        p2 = get_progress()
        assert p2["phase"] == "idle"
