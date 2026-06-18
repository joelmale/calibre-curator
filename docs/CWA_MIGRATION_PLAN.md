# Migration Plan: Calibre-Web fork → Calibre-Web-Automated (CWA)

**Status:** Deployed 2026-06-18 (commit 6a994db, live via Dockhand stack 6) · **Date:** 2026-06-18 · **Owner:** JoelN

## 1. Why this is low-risk

The curator couples to its base image through a deliberately thin seam, and every
load-bearing point of that seam was verified to still exist in CWA's source:

| Coupling point | In current fork | In CWA `main`? |
|---|---|---|
| `from .web import web` (AST anchor for `patch_main.py`) | yes | ✅ `cps/main.py:23` |
| `app.register_blueprint(web)` (AST anchor) | yes | ✅ `cps/main.py:73` |
| `shelf.create_shelf` (nav anchor for `patch_layout.py`) | yes | ✅ `cps/templates/layout.html:305` |
| `cps.usermanagement.user_login_required` | yes | ✅ present |
| `cps.cw_login.current_user` | yes | ✅ `cps/cw_login/__init__.py` present |
| `cps.render_template.render_title_template` | yes | ✅ present |

**Conclusion:** `patch_main.py` and `patch_layout.py` apply to CWA *without anchor
changes*, and `ai_bridge.py`'s imports resolve unchanged. The migration is mostly a
**re-targeting + path/volume alignment** exercise, not a rewrite.

### What CWA changes about the base

- **Base image:** `ghcr.io/linuxserver/baseimage-ubuntu:noble` (multi-stage), **not**
  the `lscr.io/linuxserver/calibre-web` image we currently fork from.
- **Calibre lives at `/app/calibre`** (full official binaries: `calibredb`,
  `ebook-convert`, `ebook-polish`, `ebook-edit`, **and the calibre Python**). This is
  the single most important fact for the editor work (see `WEB_EDIT_BOOK_PLAN.md`).
- **App lives at `/app/calibre-web-automated/`** (still the `cps` Flask package).
- **Volumes:** `/config`, `/calibre-library`, `/cwa-book-ingest` (auto-ingest folder).
- **Extra daemons (s6):** auto-ingest watcher, auto-convert, EPUB-fixer, nightly
  backup zipper, library-refresh. These run inside the CWA container.
- **Already-present blueprints that overlap with us:** `duplicates` (hybrid SQL +
  fuzzy) and `editbook` (calibre-web's *metadata* editor — not the Tweak-ePub tool).

## 2. Base strategy (decision)

**Keep the existing "build FROM the published image + idempotent build-time patch"
pattern** — it is the reason this migration is cheap. Do **not** vendor/fork the whole
CWA repo. Concretely:

- Rename `calibre-web-fork/` → `cwa-fork/`.
- `Dockerfile`: `FROM ghcr.io/crocodilestick/calibre-web-automated:<PINNED_TAG>`.
- **Pin a specific tag/digest** (not `:latest`). The AST/anchor patchers self-verify
  and fail the build if upstream moves the anchors — pinning makes that failure
  happen on a deliberate version bump, never silently in prod.
- Patch paths change from `/app/calibre-web/cps/...` → `/app/calibre-web-automated/cps/...`.

## 3. Concrete change list

### 3.1 `cwa-fork/Dockerfile`
- `FROM ghcr.io/crocodilestick/calibre-web-automated:<PINNED_TAG>`.
- Update every `COPY .../app/calibre-web/...` target → `/app/calibre-web-automated/...`.
- `requests` install: confirm the interpreter CWA runs `cps` under. CWA uses system
  python at `/app/calibre-web-automated` with its own deps (not the old `/lsiopy`
  venv). Install with the matching `pip` (likely plain `pip3`); `requests` is very
  likely already present (cps uses it) — verify and drop the line if redundant.
- Re-point both patch invocations to the `calibre-web-automated` path.

### 3.2 `cwa-fork/cps/ai_bridge.py`
- `_CALIBRE_LIB` default `/books` → **`/calibre-library`** (match CWA + the sidecar,
  which already uses `/calibre-library`).
- `_CALIBREDB`: today `shutil.which("calibredb") or "/usr/bin/calibredb"`. In CWA the
  binary is at `/app/calibre/calibredb`. Confirm `/app/calibre` is on `PATH` inside
  the container; if not, change the fallback to `/app/calibre/calibredb`.
- No change to auth/admin/proxy logic.

### 3.3 `compose.yaml`
- Service `calibre-web` → build context `./cwa-fork`; rename to `cwa` (optional but
  clearer). Container name e.g. `calibre-web-automated`.
- Volumes: add CWA's expected mounts — `/config`, `/calibre-library` (rw),
  `/cwa-book-ingest`. Map the host calibre dir to **`/calibre-library`** (it is
  currently mounted to both `/books` in the fork and `/calibre-library` in the
  sidecar — unify on `/calibre-library`).
- Env: keep `AI_SIDECAR_*`. Add CWA-specific env as desired (`CWA_PORT_OVERRIDE`,
  `NETWORK_SHARE_MODE` if the library is on NFS/SMB — your library is on
  `/mnt/books-nas-vol3`, so evaluate `NETWORK_SHARE_MODE=true`).
- Sidecar service: library mount stays `:ro` (it only reads). Writeback continues to
  go *through the CWA container's `calibredb`* via the bridge — keep a single writer.

### 3.4 `build.sh` / `scripts/deploy-sidecar.sh`
- Update the build context path and any `calibre-web-fork` references.
- Add a post-build assertion that the patchers succeeded (they already `sys.exit(non-0)`
  on a missed anchor — surface that as a hard build failure, which `docker build`
  already does).

### 3.5 `.env.example`
- Document the pinned CWA tag and any new CWA env knobs.

## 4. Feature-overlap rationalization ("refine the sidecar")

CWA now owns several capabilities the curator built itself. Decide per row:

| Curator feature | CWA equivalent | Recommendation |
|---|---|---|
| Duplicate Detector (`/ai/duplicates`) | `duplicates` blueprint (SQL + fuzzy) | **Keep only the semantic/embedding near-dup** as a differentiator; retire exact/fuzzy-title matching and link out to CWA's page, or drop the curator page entirely. |
| Format Scrub (`/ai/scrub`) | none direct (auto-convert reduces need) | **Keep.** Genuinely useful and unique. |
| Metadata Enrichment (LLM tags/desc) | CWA "metadata enforcement" writes UI edits into the book files | **Keep — now complementary.** Enrichment writeback via `calibredb` now benefits from CWA enforcement propagating into the files. |
| Semantic Collections | CWA "Magic Shelves" (rule-based) | **Keep semantic/embedding-clustered collections;** let CWA own rule-based shelves. Avoid building rule-based shelves in the curator. |
| Semantic search / Mood / Sequences / Recommendations / multi-provider Chat | none | **Keep all — these are the reason the curator exists.** |

Net effect: the sidecar sheds the bits CWA does better (exact dup detection, rule
shelves) and doubles down on the AI-native features.

## 5. Phasing

- **M0 — Spike (½ day).** Build `cwa-fork` FROM CWA with a pinned tag; run the existing
  patchers; `docker compose up`; confirm: app boots, the "AI Curated Library" nav entry
  renders inside CWA's theme, `/ai/` dashboard loads, `/ai/api/healthz` proxies to the
  sidecar. This validates the whole seam in one shot. *(Anchors already verified, so
  this should pass.)*
- **M1 — Paths & volumes.** §3.1–3.5. Unify on `/calibre-library`; fix `calibredb` path;
  pin tag; update build/deploy scripts.
- **M2 — Overlap rationalization.** §4 decisions; remove retired pages + their bridge
  routes + sidecar endpoints; tidy `_ai_nav.html`.
- **M3 — Verification.** Re-point/confirm enrichment & scrub writeback through CWA's
  `calibredb`; confirm admin gating under CWA auth (incl. OIDC if enabled); render-check
  every `/ai/*` page against CWA's layout/theme (Bootstrap markup may differ subtly).
- **M4 — Cutover.** Run `docs/QA_TEST_PLAN.md`; flip prod compose to `cwa-fork`; delete
  `calibre-web-fork/`; archive the old image.

## 6. Risks & mitigations

- **Upstream anchor drift on version bump.** Mitigation: pinned tag + self-verifying
  patchers fail the build loudly. Bump deliberately; re-run M0 spike on each bump.
- **Two writers to the library** (CWA daemons + curator writeback). Mitigation: curator
  writes **only** via `calibredb` (which locks `metadata.db`), then calls CWA's
  library-refresh; never touch book files directly. Same discipline the editor will use.
- **Layout/theme markup differences** break the injected nav `<li>` styling. Mitigation:
  M3 render-check; the nav patch targets a stable `shelf.create_shelf` anchor.
- **`NETWORK_SHARE_MODE` / WAL on NAS.** Library is on `/mnt/books-nas-vol3`. Evaluate
  CWA's `NETWORK_SHARE_MODE` to avoid SQLite WAL corruption over SMB/NFS.
- **`requests`/python-env assumptions** in the bridge Dockerfile. Mitigation: verify in
  the M0 spike; adjust the pip line to CWA's interpreter.

## 7. Definition of done
- `cwa-fork` image builds from a pinned CWA tag with patchers green.
- All retained `/ai/*` pages render and function inside CWA; retired pages removed.
- Writeback (enrichment, scrub) verified through CWA `calibredb` + refresh.
- `calibre-web-fork/` deleted; docs + memory updated.
