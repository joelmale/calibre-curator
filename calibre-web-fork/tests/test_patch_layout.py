"""Tests for patch_layout.py — run from the calibre-web-fork directory."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PATCH_SCRIPT = Path(__file__).parent.parent / "patch_layout.py"

# ---------------------------------------------------------------------------
# Synthetic layout.html fixtures
# ---------------------------------------------------------------------------

def _make_layout(anchor_snippet: str) -> str:
    return f"""\
<!DOCTYPE html>
<html>
<body>
<ul class="nav">
  <li><a href="/">Home</a></li>
  {anchor_snippet}
  <li><a href="/about">About</a></li>
</ul>
</body>
</html>
"""

LAYOUT_SHELF_LIST = _make_layout(
    "<li><a href=\"{{ url_for('shelf.shelf_list') }}\">Shelves</a></li>"
)

LAYOUT_CREATE_SHELF = _make_layout(
    "<li><a href=\"{{ url_for('shelf.create_shelf') }}\">Create Shelf</a></li>"
)

LAYOUT_BOOKS_LIST = _make_layout(
    "<li><a href=\"{{ url_for('web.books_list') }}\">Books</a></li>"
)

LAYOUT_NO_ANCHOR = _make_layout(
    "<li><a href=\"/other\">Other</a></li>"
)


def _run_patch(tmp_path: Path, content: str) -> tuple[Path, subprocess.CompletedProcess[str]]:
    f = tmp_path / "layout.html"
    f.write_text(content)
    result = subprocess.run(
        [sys.executable, str(PATCH_SCRIPT), str(f)],
        capture_output=True, text=True,
    )
    return f, result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPatchLayoutAnchors:
    def test_patches_shelf_list_anchor(self, tmp_path):
        f, result = _run_patch(tmp_path, LAYOUT_SHELF_LIST)
        assert result.returncode == 0
        assert "ai_bridge.dashboard" in f.read_text()

    def test_patches_create_shelf_anchor(self, tmp_path):
        f, result = _run_patch(tmp_path, LAYOUT_CREATE_SHELF)
        assert result.returncode == 0
        assert "ai_bridge.dashboard" in f.read_text()

    def test_patches_books_list_anchor(self, tmp_path):
        f, result = _run_patch(tmp_path, LAYOUT_BOOKS_LIST)
        assert result.returncode == 0
        assert "ai_bridge.dashboard" in f.read_text()

    def test_nav_entry_inserted_before_anchor_li(self, tmp_path):
        f, _ = _run_patch(tmp_path, LAYOUT_SHELF_LIST)
        content = f.read_text()
        ai_pos = content.find("ai_bridge.dashboard")
        shelf_pos = content.find("shelf.shelf_list")
        assert ai_pos < shelf_pos, "AI nav entry should appear before the shelf anchor"

    def test_svg_icon_present(self, tmp_path):
        f, _ = _run_patch(tmp_path, LAYOUT_SHELF_LIST)
        assert "<svg" in f.read_text()

    def test_exits_nonzero_when_no_anchor(self, tmp_path):
        _, result = _run_patch(tmp_path, LAYOUT_NO_ANCHOR)
        assert result.returncode != 0


class TestPatchLayoutIdempotent:
    def test_second_run_is_noop(self, tmp_path):
        f, _ = _run_patch(tmp_path, LAYOUT_SHELF_LIST)
        content_after_first = f.read_text()

        result = subprocess.run(
            [sys.executable, str(PATCH_SCRIPT), str(f)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert f.read_text() == content_after_first

    def test_second_run_does_not_duplicate_entry(self, tmp_path):
        f, _ = _run_patch(tmp_path, LAYOUT_SHELF_LIST)
        _run_patch(tmp_path, f.read_text())
        assert f.read_text().count("ai_bridge.dashboard") == 1
