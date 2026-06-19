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
EDITOR_BASE_URL  = os.getenv("AI_EDITOR_BASE_URL", "http://calibre-web-editor:8091").rstrip("/")
ALLOWED_METHODS  = {"GET", "POST"}

# ── Calibre library config ────────────────────────────────────────────────────

_CALIBRE_LIB  = os.getenv("CALIBRE_LIBRARY_ROOT", "/calibre-library")
_CALIBRE_DB   = os.path.join(_CALIBRE_LIB, "metadata.db")
_CALIBREDB    = shutil.which("calibredb") or "/app/calibre/calibredb"
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


# ── Chat provider rate limits ──────────────────────────────────────────────────

@ai_bridge.route("/providers", methods=["GET"])
@user_login_required
def providers_index():
    if not _is_admin():
        abort(403)
    return render_title_template(
        "ai_providers.html",
        title="Provider Limits",
        page="ai-providers",
    )


@ai_bridge.route("/providers/save", methods=["POST"])
@user_login_required
def providers_save():
    if not _is_admin():
        return jsonify({"error": "admin_required"}), 403
    body = request.get_json(silent=True) or {}
    data, status = _sidecar_post("providers/limits", {
        "provider": body.get("provider"),
        "rpm": body.get("rpm"),
        "rph": body.get("rph"),
        "enabled": body.get("enabled", True),
    })
    return jsonify(data), status


# ── Metadata enrichment (Feature 4) ────────────────────────────────────────────

@ai_bridge.route("/enrichment", methods=["GET"])
@user_login_required
def enrichment_index():
    if not _is_admin():
        abort(403)
    return render_title_template(
        "ai_enrichment.html",
        title="Metadata Enrichment",
        page="ai-enrichment",
        calibredb_available=os.path.isfile(_CALIBREDB),
    )


@ai_bridge.route("/enrichment/audit", methods=["GET"])
@user_login_required
def enrichment_audit():
    if not _is_admin():
        return jsonify({"error": "admin_required"}), 403

    limit = min(int(request.args.get("limit", 50)), 500)
    
    # Identify books with poor metadata directly from calibre DB
    query = """
        SELECT 
            b.id as bookId, b.title, b.author_sort as authorSort,
            c.text as description,
            (SELECT COUNT(*) FROM books_tags_link btl WHERE btl.book = b.id) as tag_count
        FROM books b
        LEFT JOIN comments c ON c.book = b.id
        ORDER BY b.id DESC
    """
    
    results = []
    with _calibre_conn() as conn:
        rows = conn.execute(query).fetchall()
        
    for r in rows:
        issues = []
        if not r["description"] or not r["description"].strip():
            issues.append("Missing description")
        if r["tag_count"] == 0:
            issues.append("No tags")
            
        title = r["title"] or ""
        if "_" in title or ".epub" in title.lower() or ".azw3" in title.lower() or "-" in title:
            issues.append("Malformed title")
        elif title.isupper() and len(title) > 4:
            issues.append("Title in ALL CAPS")
            
        if not r["authorSort"] or r["authorSort"].lower() in ["unknown", "anonymous"]:
            issues.append("Missing author")
            
        if issues:
            results.append({
                "bookId": r["bookId"],
                "title": title,
                "authorSort": r["authorSort"] or "",
                "issues": issues,
                "score": len(issues)
            })
            
    # Sort by score (worst first), then slice
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return jsonify({
        "totalCandidates": len(results),
        "books": results[:limit]
    })


def _sidecar_post(subpath: str, payload: dict) -> tuple[dict, int]:
    """POST JSON to the sidecar API and return (json, status)."""
    url = f"{SIDECAR_BASE_URL}/api/v1/{subpath}"
    try:
        resp = requests.post(url, headers=_sidecar_headers(), json=payload, timeout=60)
    except requests.RequestException as exc:
        return {"error": "sidecar_unavailable", "detail": str(exc)}, 503
    try:
        return resp.json(), resp.status_code
    except ValueError:
        return {"error": "bad_sidecar_response"}, resp.status_code


@ai_bridge.route("/enrichment/apply", methods=["POST"])
@user_login_required
def enrichment_apply():
    """Write approved metadata back to Calibre via calibredb, then record the
    review in the sidecar. Per-field: a field is written only if approved."""
    if not _is_admin():
        return jsonify({"error": "admin_required"}), 403
    if not os.path.isfile(_CALIBREDB):
        return jsonify({"error": f"calibredb not found at {_CALIBREDB}"}), 503

    body = request.get_json(silent=True) or {}
    try:
        book_id = int(body["bookId"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "bookId is required"}), 400

    apply_tags = body.get("tags")          # list[str] or None (None = not approved)
    apply_desc = body.get("description")   # str or None
    reading_level = body.get("readingLevel")

    fields: list[str] = []
    if isinstance(apply_tags, list):
        fields += ["--field", "tags:" + ",".join(str(t) for t in apply_tags)]
    if isinstance(apply_desc, str) and apply_desc.strip():
        fields += ["--field", f"comments:{apply_desc.strip()}"]

    if not fields:
        return jsonify({"error": "nothing to apply — no approved fields"}), 400

    writeback_status = "applied"
    writeback_error: str | None = None
    try:
        proc = subprocess.run(
            [_CALIBREDB, "--with-library", _CALIBRE_LIB,
             "set_metadata", str(book_id), *fields],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            writeback_status = "failed"
            writeback_error = (proc.stderr or proc.stdout or "calibredb error").strip()
    except Exception as exc:
        writeback_status = "failed"
        writeback_error = str(exc)

    # Record the decision in the sidecar audit log regardless of outcome.
    _sidecar_post("enrichment/review", {
        "bookId": book_id,
        "appliedTags": apply_tags if isinstance(apply_tags, list) else None,
        "appliedDescription": apply_desc if isinstance(apply_desc, str) else None,
        "appliedReadingLevel": reading_level,
        "decision": body.get("decision") or {},
        "writebackStatus": writeback_status,
        "writebackError": writeback_error,
    })

    if writeback_status == "failed":
        return jsonify({"error": "writeback_failed", "detail": writeback_error}), 500
    return jsonify({"ok": True, "bookId": book_id})


@ai_bridge.route("/enrichment/apply/batch", methods=["POST"])
@user_login_required
def enrichment_apply_batch():
    if not _is_admin():
        return jsonify({"error": "admin_required"}), 403
    if not os.path.isfile(_CALIBREDB):
        return jsonify({"error": f"calibredb not found at {_CALIBREDB}"}), 503

    body = request.get_json(silent=True) or {}
    items = body.get("items", [])
    if not isinstance(items, list):
        return jsonify({"error": "items must be a list"}), 400

    results = []
    
    # We execute each application synchronously but quickly, calibredb is fast enough
    # for batches of 10-20.
    for item in items:
        try:
            book_id = int(item["bookId"])
        except (KeyError, TypeError, ValueError):
            results.append({"error": "Invalid bookId", "item": item})
            continue

        apply_tags = item.get("tags")
        apply_desc = item.get("description")
        reading_level = item.get("readingLevel")

        fields = []
        if isinstance(apply_tags, list):
            fields += ["--field", "tags:" + ",".join(str(t) for t in apply_tags)]
        if isinstance(apply_desc, str) and apply_desc.strip():
            fields += ["--field", f"comments:{apply_desc.strip()}"]

        if not fields:
            results.append({"bookId": book_id, "status": "skipped", "error": "No fields approved"})
            continue

        writeback_status = "applied"
        writeback_error = None
        try:
            proc = subprocess.run(
                [_CALIBREDB, "--with-library", _CALIBRE_LIB,
                 "set_metadata", str(book_id), *fields],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                writeback_status = "failed"
                writeback_error = (proc.stderr or proc.stdout or "calibredb error").strip()
        except Exception as exc:
            writeback_status = "failed"
            writeback_error = str(exc)

        _sidecar_post("enrichment/review", {
            "bookId": book_id,
            "appliedTags": apply_tags if isinstance(apply_tags, list) else None,
            "appliedDescription": apply_desc if isinstance(apply_desc, str) else None,
            "appliedReadingLevel": reading_level,
            "decision": item.get("decision") or {},
            "writebackStatus": writeback_status,
            "writebackError": writeback_error,
        })
        
        results.append({
            "bookId": book_id,
            "status": writeback_status,
            "error": writeback_error
        })

    return jsonify({"ok": True, "results": results})


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

# ── Editor Proxy ──────────────────────────────────────────────────────────────

@ai_bridge.route("/editor/<int:book_id>/<format>", methods=["GET"])
@user_login_required
def editor_page(book_id: int, format: str):
    if not _is_admin():
        abort(403)
    return render_title_template(
        "ai_dashboard.html",  # Reuses dashboard HTML which mounts our JS
        title="Edit Book",
        page="ai-editor",
        # Pass variables if needed, though frontend can extract from URL
    )

@ai_bridge.route("/editor/api/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
@user_login_required
def proxy_editor_api(subpath: str) -> Response:
    if not _is_admin():
        abort(403)
        
    url = f"{EDITOR_BASE_URL}/api/v1/{subpath}"
    
    # We don't use sidecar_headers because the editor doesn't use the shared token yet.
    headers = {}
    if request.content_type:
        headers["Content-Type"] = request.content_type
        
    try:
        editor_response = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            timeout=120,
        )
    except requests.RequestException as exc:
        return jsonify({"error": "editor_unavailable", "detail": str(exc)}), 503

    return Response(
        response=editor_response.content,
        status=editor_response.status_code,
        content_type=editor_response.headers.get("Content-Type", "application/octet-stream"),
    )
