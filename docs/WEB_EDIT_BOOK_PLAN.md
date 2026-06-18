# Plan: Calibre "Edit Book" (Tweak ePub) as a web app, alongside CWA

**Status:** Proposed · **Date:** 2026-06-18 · **Owner:** JoelN

Goal: reproduce Calibre desktop's **Edit Book** tool (the full HTML/CSS "Tweak ePub"
editor — *not* the metadata editor) as a browser experience, layered on CWA. Supports
EPUB2/3, AZW3, KEPUB.

## 1. The key enabler

Calibre's Edit Book is a Qt GUI over a headless, importable Python core:
`calibre.ebooks.oeb.polish.*`. **CWA already bundles the full calibre Python at
`/app/calibre`**, so we do **not** reimplement ebook logic — we drive calibre's own
`Container` + polish tools and build only the *web UI* and a thin API around them.

The polish core gives us, out of the box (all verified against the calibre manual):

- **Container model** — `get_container(path, tweak_mode=True)`; `.parsed(name)`,
  `.replace(name,obj)`, `.open(name,mode)`, `.add_file`, `.remove_item`, `.rename`,
  `.commit(outpath)`. A book = root folder + OPF + manifest/spine.
- **Cover** — `cover.set_cover`, `mark_as_cover`, `mark_as_titlepage`.
- **ToC** — `toc.get_toc`, `commit_toc`, generators `from_xpaths` / `from_links` /
  `from_files`, `create_inline_toc`.
- **Search/replace & file ops** — `replace.rename_files`, `replace_links`,
  `get_recommended_folders` (arrange into folders).
- **Split/merge** — `split_merge.split` / `multisplit` / `merge`.
- **Pretty/fix** — `pretty.fix_all_html` (HTML5 well-formedness), `pretty_all`,
  `pretty_html/_css/_xml`.
- **CSS** — `css.remove_unused_css`, `filter_css`.
- **Fonts** — `fonts.change_font`; plus `subset_all_fonts`, `embed_all_fonts`.
- **Jacket** — `jacket.add_or_replace_jacket`, `remove_jacket`.
- **Checks** — `check_book.run_checks` + `fix_errors` (auto-fix where possible).
- **Reports** — `report.gather_data` (powers the GUI's Files/Images/Links/Words/CSS).
- **Spell** — `spell.*` extracts words+positions; pair with calibre/hunspell dictionaries.

## 2. Runtime architecture (decision)

The editor backend must run where **calibre's Python + the library** are. Two viable
topologies — recommendation first:

### ✅ Recommended: standalone `cwa-editor` service, `FROM` the CWA image
Preserves the project's core value (**minimal CWA-fork diff**) while getting
`/app/calibre` and `calibredb` for free.

```
Browser ──▶ CWA fork (8083)
              │  ai_bridge proxies /ai/editor/* (auth + nav, ~unchanged diff)
              ▼
        cwa-editor service  (FROM crocodilestick/calibre-web-automated:<pin>)
          ├─ API process  (system python: Flask + WebSocket; file CRUD, preview, routing)
          └─ polish worker (warm `calibre-debug` process: imports calibre.* ; JSON-RPC
                            over a local unix socket; runs container/tool/commit ops)
          mounts: /calibre-library (rw, for commit via calibredb)
                  editor_scratch  (rw, exploded edit sessions + checkpoints)
```

Why two processes: Flask/gunicorn aren't in calibre's *bundled* site-packages, and
calibre's frozen Python isn't pip-friendly. So the web layer runs under the container's
ordinary python, and a **persistent** `calibre-debug worker.py` (started once, ~1s warm
cost) imports `calibre.ebooks.oeb.polish.*` and answers JSON-RPC calls. File reads/writes
and preview are pure filesystem and never touch the worker — only *tools / checks /
reports / ToC / spell / commit* do.

The CWA fork only gains: a proxy route family `/ai/editor/*` and one nav entry — i.e.
the **same minimal-diff pattern already in use** for the AI sidecar.

### Alternative: embed the worker *inside* the CWA container
Add the calibre-debug worker as an s6 service in `cwa-fork` and expose editor routes
directly from `ai_bridge`. Pros: library already rw, `calibredb` local, no second image.
Cons: grows the fork diff and ties the editor's lifecycle to CWA. Choose this only if
you'd rather not run a second container.

> **Single-writer rule (both topologies):** commit **only** via `calibredb`
> (`add_format --replace`), then ping CWA's library-refresh. Never overwrite book files
> directly while CWA's daemons run. `calibredb` locks `metadata.db` → safe concurrency.

## 3. Session & data model

An **edit session = an exploded working directory + a metadata row**, mirroring how
calibre's own checkpoints work (it copies the container folder).

```
editor_scratch/<session_id>/
  book/            ← exploded ebook (OPF + HTML/CSS/img/fonts), the live working tree
  checkpoints/<label>/   ← full copies (or hardlink trees) for snapshot-undo
  session.json     ← book_id, format, source path, dirty flag, lock owner, created_at
```

- **Open:** copy the format file out of the library → `book/` via
  `get_container(src, tweak_mode=True)` then `container.commit(work_dir)` (or unzip for
  epub); record session; take checkpoint `Original`.
- **File CRUD:** plain filesystem ops on `book/` (fast, no worker). Path-traversal
  guarded; writes confined to the session dir.
- **Tools / checks / reports / toc / spell:** worker opens a `Container` over `book/`,
  auto-checkpoints, runs the polish fn, writes back into `book/`, returns a report log.
- **Checkpoint / restore:** copy `book/` ↔ `checkpoints/<label>/`.
- **Commit (Save to library):** worker `container.commit(<new file>)` → API calls
  `calibredb add_format --replace <book_id> <file>` (optionally archive the prior format
  first) → ping CWA refresh → clear dirty flag.
- **Concurrency:** advisory lock per `(book_id, format)`; one active session each;
  sessions GC'd after idle TTL (configurable).

Session metadata persists in SQLite (reuse the sidecar's schema-on-boot pattern, or a
small dedicated DB in the editor service) so sessions survive a restart.

## 4. Frontend (extends the existing Vite + TS + Web Components app)

A new full-screen `AiEditBookPage` (route `/ai/editor/<book_id>/<format>`), built from
the existing atoms→organisms convention:

- **File tree organism** — grouped Text / Styles / Images / Fonts / Misc (from OPF
  manifest+spine media-types), like calibre. Add/rename/delete/reorder-spine actions.
- **Editor organism** — **CodeMirror 6** tabs: `@codemirror/lang-html`, `-css`, `-xml`,
  `-javascript`; line numbers, bracket match, autocomplete; lint gutter fed by the
  server `check_book` results. Inline formatting toolbar (bold/italic/headings/insert
  link+image/insert tag) operates on the CM selection.
- **Preview organism** — sandboxed `<iframe>` (no network, CSP) loading the current
  XHTML through a **preview route** that serves session files with correct content-types
  and rewrites internal hrefs to session-relative URLs and injects the book CSS.
  - MVP: one-way (debounced save → refresh).
  - Full: two-way sync — server-side parse injects `data-cm-line` attributes; click in
    preview → jump to code line, and vice-versa (calibre's approach).
- **Side panels:** ToC editor (drag reorder/renest + "generate from headings/links/
  files"), Search & Replace (Normal/Regex/Function × scope: file/all-text/all-styles/
  selected/marked), Checks (severity-grouped, jump-to, "try auto-fix"), Reports (Files/
  Images/Links/Words/CSS with "delete unused"), Spell check, Checkpoints (list + restore
  + optional diff).
- **Long ops** (subset fonts, checks, reports on big books): async job + progress via
  WebSocket/SSE.
- **Metadata:** *don't rebuild it* — deep-link to CWA's existing `editbook` metadata
  editor.

## 5. API surface (proxied as `/ai/editor/*` through the CWA bridge)

```
POST   /sessions                      {book_id, format}      → open/explode, returns session
GET    /sessions/{id}                                        → manifest, spine, dirty, lock
DELETE /sessions/{id}                                        → discard (no writeback)
GET    /sessions/{id}/files                                  → categorized file tree
GET    /sessions/{id}/file?name=...                          → raw file (editor + preview)
PUT    /sessions/{id}/file?name=...   <body>                 → save file
POST   /sessions/{id}/file            {name,media_type,data} → add file
POST   /sessions/{id}/rename          {map:{old:new}}        → rename_files (+ relink)
DELETE /sessions/{id}/file?name=...                          → remove_item
POST   /sessions/{id}/checkpoints     {label}                → snapshot
POST   /sessions/{id}/restore         {label}                → revert
GET    /sessions/{id}/toc  · PUT .../toc                     → get/commit ToC
POST   /sessions/{id}/toc/generate    {source:xpaths|links|files}
POST   /sessions/{id}/tool/{name}     {params}               → run a polish tool (report log)
GET    /sessions/{id}/checks · POST .../checks/fix
GET    /sessions/{id}/reports/{kind}
POST   /sessions/{id}/search          {mode,scope,find,replace?,count?}
GET    /sessions/{id}/spell · POST .../spell/replace
POST   /sessions/{id}/commit          {archive_original?}    → calibredb add_format --replace
GET    /preview/{id}/*                                        → sandboxed file serving for iframe
```

`tool/{name}` dispatches to an **allowlisted** map → polish functions: `add_cover`,
`mark_cover`, `mark_titlepage`, `embed_fonts`, `subset_fonts`, `smarten_punct`,
`remove_unused_css`, `filter_css`, `beautify`, `fix_html`, `inline_toc`, `add_jacket`,
`remove_jacket`, `split`, `merge`, `change_font`, `arrange_into_folders`.

## 6. Phasing (MVP → parity)

- **E0 — Round-trip skeleton.** `cwa-editor` service (FROM CWA) + warm calibre-debug
  worker; open/explode a book; file tree; read/save a single file in CodeMirror;
  checkpoints (`Original` + manual); **commit → `calibredb add_format --replace` →
  refresh**. *Exit:* edit one HTML file, save to library, see it in CWA.
- **E1 — Real editing.** Multi-file tabs; add/remove/rename files (with relink); image &
  font handling; live **preview (one-way)**; **cover tool**.
- **E2 — Tools & integrity.** ToC editor + generators; **Reports** (Files/Images/Links/
  Words/CSS); **Check Book + auto-fix**; core tools: beautify, fix-HTML, remove-unused-
  CSS, embed/subset fonts, jacket, inline-ToC.
- **E3 — Power editing.** Search & Replace (regex + across selected files); two-way
  preview sync; inline formatting toolbar; split/merge; arrange-into-folders.
- **E4 — Parity polish.** Spell check (multi-language dictionaries); saved searches;
  snippets/marked-text; checkpoint diff/compare; (sandboxed) function-mode replace;
  AZW3/KEPUB commit paths hardened.

## 7. Risks & decisions

- **Running a web server under calibre's python** — resolved by the two-process design
  (Flask under system python + warm `calibre-debug` JSON-RPC worker). Validate the IPC
  in E0; fall back to a single-process stdlib WSGI server under `calibre-debug` if the
  split proves awkward.
- **Concurrency vs CWA daemons** — single-writer rule (§2): commit only via `calibredb`,
  then refresh. Auto-ingest watches `/cwa-book-ingest`, *not* the library, so editor
  writeback won't trip the watcher.
- **Function-mode search/replace = arbitrary Python.** Defer to E4 and sandbox (no FS/
  net, CPU/time-limited), or expose only a curated function library. Never run user
  Python unsandboxed in a shared service.
- **Preview safety** — iframe `sandbox` + CSP + no network; serve only from the session
  dir; strip/neutralize scripts in preview.
- **Big books / long ops** — async jobs + progress; cap session count + idle GC; cap file
  sizes loaded into the editor.
- **Format coverage** — Container supports EPUB + AZW3 (KEPUB is an EPUB variant). MOBI/
  PDF are out of scope for *structural* editing (convert-to-EPUB first via CWA). State
  this in the UI.
- **AZW3 fidelity** — commit/round-trip AZW3 is lossier than EPUB; test explicitly in E4.

## 8. Open decisions for sign-off
1. **Topology:** standalone `cwa-editor` service (recommended, keeps fork diff minimal)
   vs. worker embedded in the CWA container.
2. **Scope of v1:** ship E0–E2 (a genuinely useful editor) first, or hold for E0–E4
   parity before release?
3. **Overlap with CWA `editbook`:** confirm we link out to CWA for *metadata* and own
   only the *structural/HTML/CSS* editor (recommended), to avoid two metadata editors.
