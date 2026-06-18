from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone

import requests
from flask import Blueprint, Response, abort, jsonify, request
from .usermanagement import user_login_required
from .render_template import render_title_template

ai_bridge = Blueprint("ai_bridge", __name__, url_prefix="/ai")


def _is_admin() -> bool:
    # calibre-web bundles its own cw_login rather than using the flask_login PyPI
    # package — import from there to get the active current_user proxy.
    from .cw_login import current_user  # noqa: PLC0415
    return bool(current_user.role_admin())

# ── Sidecar proxy config ──────────────────────────────────────────────────────

SIDECAR_BASE_URL = os.getenv("AI_SIDECAR_BASE_URL", "http://ai-sidecar:8090").rstrip("/")
SIDECAR_TOKEN    = os.getenv("AI_SIDECAR_SHARED_TOKEN", "")
SIDECAR_ENABLED  = os.getenv("AI_SIDECAR_ENABLED", "false").lower() == "true"
ALLOWED_METHODS  = {"GET", "POST"}

# ── Calibre library config ────────────────────────────────────────────────────

_CALIBRE_LIB  = os.getenv("CALIBRE_LIBRARY_ROOT", "/books")
_CALIBRE_DB   = os.path.join(_CALIBRE_LIB, "metadata.db")
_CALIBREDB    = shutil.which("calibredb") or "/usr/bin/calibredb"
_MAX_EXECUTE  = 500       # hard cap on a single execute run
_SCRUB_LOCK   = threading.Lock()


# ── Sidecar helpers ───────────────────────────────────────────────────────────

def _sidecar_headers() -> dict[str, str]:
    if not SIDECAR_TOKEN:
        abort(503)
    return {
        "Authorization": f"Bearer {SIDECAR_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _pseudonymous_user_key(user_id: int) -> str:
    return hmac.new(
        SIDECAR_TOKEN.encode("utf-8"),
        f"calibre-user:{user_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── Format-scrub helpers ──────────────────────────────────────────────────────

def _calibre_conn() -> sqlite3.Connection:
    """Open Calibre metadata.db read-only."""
    conn = sqlite3.connect(f"file:{_CALIBRE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _formats_in_library() -> list[dict]:
    """Return every format present in the library with its book count."""
    with _calibre_conn() as conn:
        rows = conn.execute(
            "SELECT format, COUNT(*) AS cnt "
            "FROM data GROUP BY format ORDER BY cnt DESC"
        ).fetchall()
    return [{"format": r["format"], "count": r["cnt"]} for r in rows]


def _scrub_plan_data(keep_format: str, limit: int) -> dict:
    """
    Read-only analysis: which books are eligible for scrubbing.

    Eligible = has keep_format AND has at least one other format.
    Protected = has other formats but NOT keep_format (never touched).
    """
    kf = keep_format.upper()

    with _calibre_conn() as conn:
        total_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]

        # Books that don't have keep_format at all → protected
        protected_count = conn.execute(
            """SELECT COUNT(DISTINCT b.id) FROM books b
               WHERE NOT EXISTS (
                   SELECT 1 FROM data d WHERE d.book = b.id AND d.format = ?
               ) AND EXISTS (
                   SELECT 1 FROM data d2 WHERE d2.book = b.id
               )""",
            (kf,),
        ).fetchone()[0]

        # Total eligible books (ignore limit for summary)
        total_eligible = conn.execute(
            """SELECT COUNT(DISTINCT b.id) FROM books b
               WHERE EXISTS (
                   SELECT 1 FROM data d WHERE d.book = b.id AND d.format = ?
               ) AND (SELECT COUNT(*) FROM data d2 WHERE d2.book = b.id) > 1""",
            (kf,),
        ).fetchone()[0]

        # Eligible books, capped to limit
        rows = conn.execute(
            """SELECT b.id, b.title, b.author_sort,
               GROUP_CONCAT(d.format, ',') AS formats
               FROM books b
               JOIN data d ON d.book = b.id
               WHERE EXISTS (
                   SELECT 1 FROM data d2 WHERE d2.book = b.id AND d2.format = ?
               )
               GROUP BY b.id
               HAVING COUNT(d.format) > 1
               ORDER BY b.id
               LIMIT ?""",
            (kf, limit),
        ).fetchall()

    plan = []
    plan_removals = 0
    for row in rows:
        all_fmts = row["formats"].split(",")
        remove = [f for f in all_fmts if f != kf]
        plan_removals += len(remove)
        plan.append({
            "bookId":        row["id"],
            "title":         row["title"],
            "authorSort":    row["author_sort"] or "",
            "keepFormats":   [kf],
            "removeFormats": remove,
        })

    return {
        "keepFormat": kf,
        "limit": limit,
        "summary": {
            "totalBooks":        total_books,
            "protectedBooks":    protected_count,
            "eligibleBooks":     total_eligible,
            "planCount":         len(plan),
            "planRemovals":      plan_removals,
        },
        "plan": plan,
    }


def _do_scrub_execute(keep_format: str, limit: int) -> dict:
    """Run calibredb remove_format for each planned book. Requires _SCRUB_LOCK."""
    kf = keep_format.upper()
    plan = _scrub_plan_data(kf, limit)
    removed = 0
    errors: list[dict] = []

    for book in plan["plan"]:
        book_id = book["bookId"]
        for fmt in book["removeFormats"]:
            try:
                proc = subprocess.run(
                    [_CALIBREDB, "--with-library", _CALIBRE_LIB,
                     "remove_format", str(book_id), fmt],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    removed += 1
                else:
                    errors.append({
                        "bookId": book_id,
                        "title":  book["title"],
                        "format": fmt,
                        "error":  (proc.stderr or proc.stdout or "unknown error").strip(),
                    })
            except Exception as exc:
                errors.append({
                    "bookId": book_id,
                    "title":  book["title"],
                    "format": fmt,
                    "error":  str(exc),
                })

    return {
        "keepFormat":   kf,
        "processedBooks": len(plan["plan"]),
        "formatsRemoved": removed,
        "errorCount":   len(errors),
        "errors":       errors,
        "executedAt":   datetime.now(timezone.utc).isoformat(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@ai_bridge.route("/", methods=["GET"])
@user_login_required
def dashboard():
    if not SIDECAR_ENABLED:
        abort(404)
    return render_title_template(
        "ai_dashboard.html",
        title="AI Curated Library",
        page="ai-dashboard",
    )


@ai_bridge.route("/scrub", methods=["GET"])
@user_login_required
def scrub_index():
    if not _is_admin():
        abort(403)
    try:
        formats = _formats_in_library()
    except Exception as exc:
        formats = []
        error = str(exc)
    else:
        error = None

    return render_title_template(
        "ai_scrub.html",
        title="Format Scrub",
        page="ai-scrub",
        formats=formats,
        calibredb_available=os.path.isfile(_CALIBREDB),
        error=error,
    )


@ai_bridge.route("/scrub/plan", methods=["POST"])
@user_login_required
def scrub_plan():
    if not _is_admin():
        return jsonify({"error": "admin_required"}), 403

    body = request.get_json(silent=True) or {}
    keep_format = str(body.get("keepFormat", "")).strip().upper()
    limit = min(int(body.get("limit", 50)), _MAX_EXECUTE)

    if not keep_format:
        return jsonify({"error": "keepFormat is required"}), 400

    try:
        data = _scrub_plan_data(keep_format, limit)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(data)


@ai_bridge.route("/scrub/execute", methods=["POST"])
@user_login_required
def scrub_execute():
    if not _is_admin():
        return jsonify({"error": "admin_required"}), 403

    body = request.get_json(silent=True) or {}
    keep_format = str(body.get("keepFormat", "")).strip().upper()
    limit = min(int(body.get("limit", 0)), _MAX_EXECUTE)
    confirmed = body.get("confirm") is True

    if not keep_format:
        return jsonify({"error": "keepFormat is required"}), 400
    if limit <= 0:
        return jsonify({"error": "limit must be > 0 and <= 500"}), 400
    if not confirmed:
        return jsonify({"error": "confirm must be true"}), 400
    if not os.path.isfile(_CALIBREDB):
        return jsonify({"error": f"calibredb not found at {_CALIBREDB}"}), 503

    if not _SCRUB_LOCK.acquire(blocking=False):
        return jsonify({"error": "A scrub is already running — try again shortly"}), 409

    try:
        result = _do_scrub_execute(keep_format, limit)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        _SCRUB_LOCK.release()

    return jsonify(result)


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
