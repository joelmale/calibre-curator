"""Tests for patch_main.py — run from the calibre-web-fork directory."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PATCH_SCRIPT = Path(__file__).parent.parent / "patch_main.py"

# ---------------------------------------------------------------------------
# Synthetic main.py fixtures
# ---------------------------------------------------------------------------

# Module-level imports (classic style)
MAIN_MODULE_LEVEL = """\
from flask import Flask
from .web import web
from .basic import basic
from .shelf import shelf

def create_app():
    app = Flask(__name__)
    app.register_blueprint(web)
    app.register_blueprint(basic)
    return app
"""

# Imports inside a function block (current linuxserver style)
MAIN_INDENTED = """\
def create_app():
    from flask import Flask
    from .web import web
    from .basic import basic
    from .shelf import shelf
    app = Flask(__name__)
    app.register_blueprint(web)
    app.register_blueprint(basic)
    return app
"""

# Nested indentation (defensive)
MAIN_DOUBLE_INDENTED = """\
class AppFactory:
    @staticmethod
    def create():
        from .web import web
        from .basic import basic
        app = object()
        app.register_blueprint(web)
        app.register_blueprint(basic)
        return app
"""


def _run_patch(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "main.py"
    f.write_text(content)
    result = subprocess.run(
        [sys.executable, str(PATCH_SCRIPT), str(f)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"patch failed:\n{result.stdout}\n{result.stderr}"
    return f


# ---------------------------------------------------------------------------
# Correctness tests
# ---------------------------------------------------------------------------

class TestPatchMainModuleLevel:
    def test_produces_valid_python(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_MODULE_LEVEL)
        ast.parse(f.read_text())  # raises SyntaxError if broken

    def test_import_line_present(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_MODULE_LEVEL)
        assert "from .ai_bridge import ai_bridge" in f.read_text()

    def test_register_line_present(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_MODULE_LEVEL)
        assert "app.register_blueprint(ai_bridge)" in f.read_text()


class TestPatchMainIndented:
    """The bug that was caught by the live deployment."""

    def test_produces_valid_python(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_INDENTED)
        ast.parse(f.read_text())

    def test_import_indentation_matches_anchor(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_INDENTED)
        lines = f.read_text().splitlines()
        anchor_indent = next(
            len(l) - len(l.lstrip()) for l in lines if "from .web import web" in l
        )
        inserted_indent = next(
            len(l) - len(l.lstrip()) for l in lines if "from .ai_bridge import ai_bridge" in l
        )
        assert anchor_indent == inserted_indent

    def test_register_indentation_matches_anchor(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_INDENTED)
        lines = f.read_text().splitlines()
        anchor_indent = next(
            len(l) - len(l.lstrip()) for l in lines if "app.register_blueprint(web)" in l
        )
        inserted_indent = next(
            len(l) - len(l.lstrip()) for l in lines if "app.register_blueprint(ai_bridge)" in l
        )
        assert anchor_indent == inserted_indent


class TestPatchMainDoubleIndented:
    def test_produces_valid_python(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_DOUBLE_INDENTED)
        ast.parse(f.read_text())


class TestPatchMainIdempotent:
    def test_second_run_is_noop(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_INDENTED)
        content_after_first = f.read_text()

        result = subprocess.run(
            [sys.executable, str(PATCH_SCRIPT), str(f)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert f.read_text() == content_after_first

    def test_second_run_does_not_duplicate_import(self, tmp_path):
        f = _run_patch(tmp_path, MAIN_MODULE_LEVEL)
        _run_patch(tmp_path, f.read_text())
        count = f.read_text().count("from .ai_bridge import ai_bridge")
        assert count == 1


class TestPatchMainMissingAnchor:
    def test_exits_nonzero_when_anchor_missing(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("# empty file with no anchors\n")
        result = subprocess.run(
            [sys.executable, str(PATCH_SCRIPT), str(f)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
