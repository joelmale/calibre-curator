# Calibre Curator — QA & Testing Plan

> Senior QA audit of the development session that produced commits `43d089f`…`aaefe7d`.
> Goal: encode every failure as a fast, precise test so the same class of bug cannot
> reach a running container again.

Scope audited: `calibre-web-fork/` (Dockerfile, `patch_main.py`, `patch_layout.py`,
`cps/ai_bridge.py`), `ai-sidecar/sidecar/**`, `ai-frontend/src/{api,types}/**`,
`compose.yaml`.

**State of the code at audit time:** most of the 10 failures have already had a *point
fix* applied. This plan does **not** re-fix them — it adds the **tests that would have
caught them** and that will catch the next instance. Where a point fix left fragile or
dead code, that is flagged explicitly.

---

## 1. Root Cause Classification

### A. Build-time validation gaps  *(Failures #1, #2)*
The image was assembled from source transformations (`patch_main.py` rewriting
`main.py`, frontend bundle copied into static) with **no gate that proved the artifact
was valid before it ran**. The AST patcher could emit a syntactically broken file, and
Dockhand's `buildOnDeploy: false` could ship a stale image, and in both cases the
*first* signal was a crashing container. The systemic pattern: **transformations are
trusted instead of verified**, and the deploy pipeline does not assert "the bytes
running are the bytes I just built."

### B. Environment assumption failures  *(Failures #3, #4, #10)*
The linuxserver base image is non-standard — it runs Python from `/lsiopy`, bundles its
own `cw_login` instead of the `flask_login` PyPI package, and initializes an
`app.db`/anonymous-user record through its s6 boot sequence. Each failure here came from
**code written against "normal" Python/Flask assumptions** that are false in this
specific container. They are invisible on a developer laptop and only surface inside the
real image. The systemic pattern: **the test environment did not resemble the runtime
environment**, so import paths, interpreter selection, and first-boot DB state were
never exercised until production.

### C. API contract drift  *(Failures #5, #9)*
The Python sidecar and the TypeScript client agree on a JSON shape **only by
convention**. CSRF (#5) is a contract violation at the transport layer (server expects a
header the client never sent, then returns HTML instead of JSON). Field-name mismatch
(#9) is a contract violation at the payload layer (`snake_case` from SQLite rows vs.
`camelCase` TS interfaces). Both boundaries are **unchecked at build time** — the TS
compiler validates the client against its *own* hand-written interfaces, never against
what Python actually emits. The systemic pattern: **a hand-maintained interface on each
side of a wire with no single source of truth.**

### D. Pipeline correctness / state-machine gaps  *(Failure #7)*
`detect_changed_books` keys "needs work?" purely on content hashes, so a book that
*failed* but whose source is unchanged hashes identically and is never retried. The
retry path was bolted on afterward (`get_incomplete_book_ids`). The systemic pattern:
**change-detection conflated "content differs" with "work remaining,"** and there was no
test exercising the state machine across re-runs.

### E. Observability gaps  *(Failures #6, #8)*
With no root log handler, every `logger.info` was a no-op (#8), so the pipeline ran
blind. The Ollama 404 (#6) was real but surfaced as a generic "Embedding batch failed"
because the provider didn't distinguish *model absent* from *endpoint absent*. The
systemic pattern: **failures were silent or generic** — the system could not tell its
operator what was wrong, which turned 5-minute fixes into multi-hour debugging sessions.

---

## 2. Developmental Test Plan (CI / pre-commit)

Runs on every push, before any image is built or deployed. Target wall-clock: **under
90 seconds**, no network, no Ollama, no real Calibre library.

### A. Build-time validation

**A1 — AST patcher produces valid, semantically correct Python**
*What:* `patch_main.py` against (a) a realistic `main.py` fixture, (b) an
already-patched file (idempotency), (c) a file missing the anchor (must exit non-zero
with a clear message), (d) a file with CRLF endings and an indented
`register_blueprint` inside a `try:` block.
*How:* pytest, subprocess-invoke the patcher on temp files, then `ast.parse` + assert
the two lines are present at the right indentation.
*Tool:* pytest.

```python
# tests/build/test_patch_main.py
import ast, subprocess, sys, textwrap
from pathlib import Path

PATCHER = Path("calibre-web-fork/patch_main.py")

def _run(tmp: Path, src: str) -> str:
    f = tmp / "main.py"
    f.write_text(textwrap.dedent(src))
    r = subprocess.run([sys.executable, str(PATCHER), str(f)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return f.read_text()

def test_patch_is_valid_python_and_idempotent(tmp_path):
    src = """
        from .web import web
        def create_app():
            app = Flask(__name__)
            app.register_blueprint(web)
            return app
    """
    out = _run(tmp_path, src)
    ast.parse(out)                                   # never IndentationError again (#1)
    assert "from .ai_bridge import ai_bridge" in out
    assert "    app.register_blueprint(ai_bridge)" in out  # indentation preserved
    # second run must be a no-op
    f = tmp_path / "main.py"; f.write_text(out)
    r = subprocess.run([sys.executable, str(PATCHER), str(f)],
                       capture_output=True, text=True)
    assert "Already patched" in r.stdout
    assert f.read_text() == out

def test_missing_anchor_fails_loudly(tmp_path):
    f = tmp_path / "main.py"; f.write_text("x = 1\n")
    r = subprocess.run([sys.executable, str(PATCHER), str(f)],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "not found" in r.stderr
```

> The patcher already self-verifies with `ast.parse` before writing — A1 *locks that
> behavior in* and adds the CRLF / try-block / idempotency cases that the self-check
> alone doesn't prove.

**A2 — `patch_layout.py` produces valid Jinja and is idempotent**
*What:* same matrix as A1 but assert the `<li>` is injected once and the anchor-not-found
path exits non-zero.
*Tool:* pytest. (Optional: render the template with Jinja `Environment().parse()` to
catch malformed tags.)

**A3 — Docker build is part of CI, and deploy asserts image freshness**
*What:* `docker build` both images on every PR (fail the PR if the image won't build —
catches Dockerfile drift such as a bad `pip` target before deploy). At deploy time,
assert the running image digest equals the digest just built.
*How:* CI `docker build`; a post-deploy check that compares
`docker inspect --format '{{.Image}}'` of the running container to the build output (or
flips Dockhand to `buildOnDeploy: true` and verifies via the image label below).
*Tool:* `docker build`, shell assertion. See Operational gate O0 for the freshness check
that directly addresses #2.

### B. Environment assumption failures

**B1 — Flask app imports with no venv, no DB, no network**
*What:* `import sidecar.app` and `create_app()` succeed in a clean interpreter; the
import does not require a running database or Ollama. This is the unit-level analogue of
#3 (import-time `ModuleNotFoundError`).
*How:* pytest that calls `create_app()` against a temp `SIDECAR_DB_PATH` and asserts the
test client answers `/healthz`. Use `APP_ENV=test` to keep the scheduler from starting.
*Tool:* pytest.

```python
# tests/unit/test_app_imports.py
import importlib
def test_create_app_no_external_deps(tmp_path, monkeypatch):
    monkeypatch.setenv("SIDECAR_DB_PATH", str(tmp_path / "ai.sqlite3"))
    monkeypatch.setenv("AI_SIDECAR_SHARED_TOKEN", "t")
    monkeypatch.setenv("APP_ENV", "test")  # must not start the scheduler
    app_mod = importlib.import_module("sidecar.app")
    app = app_mod.create_app()
    assert app.test_client().get("/healthz").status_code == 200
```

> *Untestable-as-written flag:* `create_app()` starts the scheduler unless
> `WERKZEUG_RUN_MAIN != "true" OR app_env != "development"`. Under `APP_ENV=test` the
> scheduler **does** start (the condition is true), which can fire a real scan during
> import. **Minimal refactor:** gate scheduler start on an explicit
> `config.scheduler_enabled` (default true, set `false` in tests) instead of inferring
> from `app_env`. Until then, tests must also stub `start_scheduler`.

**B2 — `ai_bridge` admin check resolves against the right login package**
*What:* `_is_admin()` imports `current_user` from `.cw_login` (the bundled package), not
`flask_login`. Directly encodes #3 at the bridge layer.
*How:* a contract test that asserts the *source module string* used by the bridge. Since
the bridge runs inside calibre-web (not importable in sidecar CI), assert via static
check: parse `ai_bridge.py` and confirm the import target.
*Tool:* pytest + `ast`.

```python
# tests/build/test_ai_bridge_imports.py
import ast, pathlib
def test_is_admin_uses_cw_login():
    src = pathlib.Path("calibre-web-fork/cps/ai_bridge.py").read_text()
    tree = ast.parse(src)
    imports = [n.module for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and "current_user"
               in [a.name for a in n.names]]
    assert "cw_login" in imports
    assert "flask_login" not in imports     # never regress to the uninstalled package (#3)
```

**B3 — pip targets the lsiopy interpreter (Dockerfile lint)**
*What:* in `calibre-web-fork/Dockerfile`, any `pip install` must use `/lsiopy/bin/pip`
(or `/lsiopy/bin/python -m pip`), never bare `pip`. Directly encodes #4.
*How:* a tiny lint test that greps the Dockerfile.
*Tool:* pytest (or a hadolint custom rule).

```python
# tests/build/test_dockerfile_pip_target.py
import re, pathlib
def test_calibreweb_pip_uses_lsiopy():
    df = pathlib.Path("calibre-web-fork/Dockerfile").read_text()
    for line in df.splitlines():
        if re.search(r'\bpip\s+install', line):
            assert "/lsiopy/bin/pip" in line, f"pip not targeting lsiopy venv: {line!r}"
```

**B4 — First-boot DB integrity smoke (addresses #10)**
*What:* a fresh calibre-web volume must reach a state where the anonymous-user record
exists and `/` does not 500. This is environment-specific and **belongs in the
operational gate** (O3), not unit CI, because it requires the real image's s6 boot. In
CI we only assert that we never ship code assuming a pre-populated `app.db`.

### C. API contract drift  *(the highest-value section — see §6)*

**C1 — Single source of truth for the status payload**
*What:* the `/status` and `/ingestion/run` JSON shapes must match the TS interfaces
(`IAiStatusResponse`, `IIngestionTriggerResponse`, `IIngestionRunStatus`). Today
`IngestionRunRepository.get_latest()` hand-maps snake→camel (`runId`, `startedAt`, …) —
exactly the mapping that broke in #9 and could silently drift again.
*How:* generate a JSON Schema from the live Flask response and validate it; validate the
same fixtures on the TS side. See §6 for the recommended mechanism (Pydantic →
JSON Schema → `json-schema-to-typescript`). Minimum viable version now:

```python
# tests/contract/test_status_shape.py
def test_status_payload_keys(client_with_seeded_db):
    body = client_with_seeded_db.get(
        "/api/v1/status", headers={"Authorization": "Bearer t"}).get_json()
    assert set(body["library"]) == {
        "metadataDbReadable","bookCount","indexedBookCount",
        "pendingBookCount","statusBreakdown"}
    assert set(body["embedding"]) == {"provider","model","ok","warning"}
    run = body["lastIngestionRun"]
    if run is not None:
        assert set(run) == {"runId","startedAt","finishedAt","status",
            "scannedBooks","changedBooks","embeddedChunks","errorCount"}
```

```typescript
// ai-frontend/test/contract/status.contract.test.ts  (Vitest)
import statusFixture from "../fixtures/status.json";   // captured from the Python test
import type { IAiStatusResponse } from "../../src/types/status";
// Compile-time: assigning the fixture to the type fails the build if keys drift.
const _typecheck: IAiStatusResponse = statusFixture;
expect(Object.keys(statusFixture.library)).toContain("statusBreakdown");
```

**C2 — CSRF contract (transport layer, #5)**
*What:* every state-changing `fetch` from the frontend must send `X-CSRFToken`, and the
proxy must accept it. Unit-test the TS `HttpClient`: a POST includes the header read from
the `<meta name="csrf-token">` tag.
*How:* Vitest with a stubbed `document` + `fetch` spy.
*Tool:* Vitest.

```typescript
// ai-frontend/test/unit/httpClient.csrf.test.ts
it("attaches X-CSRFToken on POST", async () => {
  document.head.innerHTML = '<meta name="csrf-token" content="abc123">';
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({runId:1,status:"queued",limit:null}),
      {status:202, headers:{"Content-Type":"application/json"}}));
  await new HttpClient("/ai/api").post("/ingestion/run", {});
  const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<string,string>;
  expect(headers["X-CSRFToken"]).toBe("abc123");
});
```

**C3 — Client tolerates HTML/non-JSON error bodies**
*What:* #5 surfaced as `Unexpected token '<'` because the client blindly did
`response.json()`. Assert the client returns a structured `IApiError` (not a thrown
parse error) when the body is `<!DOCTYPE html>`.
*Tool:* Vitest.

```typescript
it("returns api_error, not a parse crash, on HTML body", async () => {
  vi.spyOn(globalThis,"fetch").mockResolvedValue(
    new Response("<!DOCTYPE html><h1>403</h1>", {status:403}));
  const res = await new HttpClient("/ai/api").get("/status");
  expect(res.ok).toBe(false);
  if (!res.ok) expect(res.error.error).toBeTypeOf("string");  // no throw
});
```

> *Code flag:* `httpClient.ts` should guard `await response.json()` in a try/catch and
> fall back to `{error:"non_json_response", detail:<status text>}`. Minimal refactor,
> high value — turns a cryptic crash into a readable error.

### D. Pipeline correctness

**D1 — Ingestion against a fixture Calibre library**
*What:* a tiny on-disk fixture library (a real `metadata.db` + a handful of files)
covering: a normal EPUB, a PDF, a **metadata-only** book (no files), a **corrupt EPUB**,
and a **zero-text** file. Run the pipeline end-to-end with a **fake embedding provider**
and an in-memory vector store, then assert per-book `ingestion_status`.
*How:* pytest, dependency-inject a `FakeEmbeddingProvider` and `FakeVectorStore`.
*Tool:* pytest.

```python
def test_pipeline_status_per_book(fixture_library, fake_provider, fake_store):
    run_pipeline_once()  # provider/store injected via config or monkeypatch
    s = status_breakdown()
    assert s["indexed"] >= 1          # the good EPUB
    assert s["failed"] >= 1           # corrupt + no-text books land in 'failed'
    # a metadata-only book with no extractable text → 'failed' "no extractable text"
```

> *Untestable-as-written flag:* `pipeline._do_run` calls `get_embedding_provider` and
> `get_vector_store` from module-level factories, so injecting fakes requires
> monkeypatching those names. **Minimal refactor:** allow `run_pipeline_once(...,
> provider=None, store=None)` to accept injected instances (default to the factories).
> This makes D1/D2 clean unit tests instead of monkeypatch-heavy ones.

**D2 — Failed books are retried on the next run (directly #7)**
See RT-07 in §4 — this is the single most important pipeline regression test.

**D3 — Hash functions are stable & order-independent**
*What:* `compute_metadata_hash` / `compute_formats_hash` return identical digests for
re-ordered authors/tags/formats, and *different* digests when a tracked field changes.
*Tool:* pytest. Cheap, pure, no I/O.

```python
def test_formats_hash_is_order_independent():
    a = record(formats=[("EPUB",10),("PDF",20)])
    b = record(formats=[("PDF",20),("EPUB",10)])
    assert compute_formats_hash(a) == compute_formats_hash(b)
```

> *Dead-code flag:* `pipeline.py:17` defines `_RETRY_STATUSES = {"failed","extracting",
> "chunked"}` but nothing reads it — the retry path uses
> `get_incomplete_book_ids()` (`NOT IN ('indexed','pending')`). These two definitions of
> "incomplete" can diverge. Either delete the constant or make the repo query derive
> from it. RT-07 pins whichever is authoritative.

### E. Observability

**E1 — Logging is actually configured**
*What:* after `create_app()`, the root logger has a `StreamHandler` at `INFO`. Encodes
#8 — guarantees `logger.info` is not a no-op.
*Tool:* pytest.

```python
def test_logging_configured(app):  # app = create_app() fixture
    import logging
    root = logging.getLogger()
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    assert root.level <= logging.INFO
```

**E2 — Ollama provider gives actionable, *distinct* errors (#6)**
*What:* model-absent 404 → `RuntimeError` mentioning `ollama pull <model>`;
endpoint-absent 404 → silent fallback to the legacy endpoint (no raise). These are
different control paths and must stay different.
*How:* pytest with `requests` mocked (`responses`/`requests-mock`), no real Ollama.
*Tool:* pytest + `responses`.

```python
def test_model_not_found_is_actionable(mock_ollama_404_model_missing):
    p = OllamaEmbeddingProvider("http://x", "nomic-embed-text")
    with pytest.raises(RuntimeError, match="ollama pull nomic-embed-text"):
        p.embed(["hi"])

def test_endpoint_404_falls_back_to_legacy(mock_embed_404_then_legacy_ok):
    p = OllamaEmbeddingProvider("http://x", "nomic-embed-text")
    assert p.embed(["hi"]) == [[0.1, 0.2]]   # used /api/embeddings, no raise
```

---

## 3. Operational Test Plan (runtime / deploy gate)

Runs against the live stack as the **deploy gate** — deploy is not "green" until these
pass. These need the real images, real Ollama, real first-boot.

**O0 — Image freshness (directly #2).** After deploy, assert the running container's
image digest matches the digest produced by this build. Practical mechanism: stamp the
image with `LABEL build.git_sha=$GIT_SHA` at build time, then
`docker inspect --format '{{ index .Config.Labels "build.git_sha"}}'` on the running
container must equal the deployed commit. Fails loudly if Dockhand reused a stale image.

**O1 — Deep startup probe (beyond `/healthz`).** `/healthz` only proves the process is
up. Add a `/readyz` that checks: (a) sidecar SQLite is writable, (b) Calibre
`metadata.db` is readable, (c) Ollama `/api/tags` reachable **and the configured model is
present**. Traffic/scheduler should not be considered ready until `/readyz` is 200.
(The status endpoint already computes the Ollama-model check — promote that logic into
`/readyz`.)

**O2 — Embedding smoke test before the scheduler scans.** On boot, embed one short probe
string (`provider.embed(["readyz probe"])`). If it raises the model-not-found
`RuntimeError`, **do not start the scheduler** — log the actionable message and stay in a
"degraded, waiting for model" state. Prevents 7,751 books churning to `failed` because a
model wasn't pulled.

**O3 — First-boot integrity (directly #10).** Bring the stack up on a *fresh*
`calibre_web_config` volume in CI-nightly or staging; assert `GET /` returns 200 (not a
redirect to `/admin/dbconfig` 500) and that the anonymous user resolves. This is the only
reliable catch for the s6/`app.db` init bug — it cannot be unit-tested.

**O4 — Canary scan of exactly one book.** Post-deploy, `POST /ai/api/ingestion/run` with
`{"limit": 1}`, then poll `/status` until `statusBreakdown.indexed >= 1` or a 120 s
timeout. Asserts the *entire* path (proxy → CSRF → sidecar → extract → chunk → embed →
vector store → status) end to end on the real stack.

**O5 — CSRF probe (directly #5).** With a valid logged-in session cookie,
`POST /ai/api/ingestion/run` and assert the response is **202 with
`Content-Type: application/json`**, not 403 and not `text/html`. A one-line `curl` in the
gate.

**O6 — Log sentinel (directly #8).** Tail container stdout for 10 s after start; assert
at least one `[INFO]` line appears (e.g. the app-factory or scheduler start line). If
logging is misconfigured again, the gate fails instead of the operator noticing days
later.

> CI vs. gate split: O1–O6 require a real Ollama and the real images, so they run in the
> **pre-deploy operational gate / staging**, never in fast PR CI. O0 is cheap and runs in
> the deploy job itself.

---

## 4. Regression Test Cases (Given / When / Then)

**RT-01 — AST patch never emits invalid Python (#1)**
*Given* a `main.py` fixture with `register_blueprint(web)` indented inside a `try:` block
and CRLF line endings
*When* `patch_main.py` runs
*Then* the output passes `ast.parse`, contains both injected lines at the correct
indentation, and a second run reports "Already patched" and changes nothing.

**RT-02 — Deploy ships the freshly built image (#2)**
*Given* a build that stamps `LABEL build.git_sha=<sha>`
*When* the stack is deployed and the container starts
*Then* the running container's `build.git_sha` label equals the deployed commit SHA.

**RT-03 — Bridge admin check uses the bundled login package (#3)**
*Given* `cps/ai_bridge.py`
*When* its imports are statically analyzed
*Then* `current_user` is imported from `cw_login`, and `flask_login` is never imported.

**RT-04 — calibre-web Dockerfile installs into the lsiopy venv (#4)**
*Given* `calibre-web-fork/Dockerfile`
*When* scanned for `pip install`
*Then* every such line uses `/lsiopy/bin/pip`.

**RT-05 — POST carries CSRF and proxy returns JSON 202 (#5)**
*Given* a logged-in session and a `csrf-token` meta tag
*When* the client POSTs to `/ai/api/ingestion/run`
*Then* the request includes `X-CSRFToken`, and the response is 202 with
`application/json` (asserted in O5 against the live stack; the header attachment is
asserted in C2 in CI).

**RT-06 — Embedding errors are distinct and actionable (#6)**
*Given* Ollama returns 404 with a "model … not found" body
*When* `OllamaEmbeddingProvider.embed` is called
*Then* it raises `RuntimeError` containing `ollama pull <model>`; *and given* a 404 with a
"page not found" body, it instead falls back to `/api/embeddings` without raising.

**RT-07 — Scanner retries failed books (#7)**
*Given* a book exists in `books_ai` with `ingestion_status = 'failed'` and a metadata hash
that matches the current Calibre record
*When* `run_pipeline_once()` runs
*Then* the book is included in the processing set (via `get_incomplete_book_ids`) and
re-processed — it is **not** skipped by `detect_changed_books`.

```python
def test_failed_book_is_retried(seeded_conn, fixture_library, fakes):
    # book 42 present in library, marked failed with matching hash
    mark_status(seeded_conn, 42, "failed")
    run_pipeline_once(provider=fakes.provider, store=fakes.store)
    assert status_of(seeded_conn, 42) in ("indexed", "chunked")
```

**RT-08 — Logging handler is installed at INFO (#8)**
*Given* a freshly created app
*When* `create_app()` returns
*Then* the root logger has a `StreamHandler` and level ≤ INFO.

**RT-09 — Status payload matches the TS contract (#9)**
*Given* a seeded sidecar DB with one finished run
*When* `GET /api/v1/status` is called
*Then* `lastIngestionRun` has exactly the keys
`{runId, startedAt, finishedAt, status, scannedBooks, changedBooks, embeddedChunks,
errorCount}` and the `library`/`embedding` key sets match their TS interfaces.

**RT-10 — Fresh stack does not 500 on `/` (#10)**
*Given* an empty `calibre_web_config` volume
*When* the stack boots and `GET /` is requested
*Then* the response is 200 (no redirect to a `/admin/dbconfig` 500) within the boot
timeout.

---

## 5. Prioritised Backlog

Ranked by **blast radius × (inverse) detectability** — i.e. how badly it breaks the
product times how easily it sneaks through today.

| Rank | Gap / Test | Failure | Blast radius | Detectability today | Effort |
|---|---|---|---|---|---|
| 1 | **API contract harness** (C1/C3/RT-09) — Python↔TS single source of truth | #5,#9 | High — every UI call | None (silent until runtime) | **M** |
| 2 | **Image-freshness gate** O0/RT-02 | #2 | High — you debug code that isn't running | None | **S** |
| 3 | **Pipeline fixture + retry test** D1/D2/RT-07 | #7 | High — whole library stuck `failed` | Low | **M** |
| 4 | **`create_app()` import + readiness** B1/O1 + scheduler-flag refactor | #3,#6,#8 | High — total outage | Low | **S–M** |
| 5 | **Ollama error-path tests** E2/RT-06 + O2 boot probe | #6 | High — 0 books embed | Low (generic error) | **S** |
| 6 | **AST patcher test matrix** A1/RT-01 | #1 | High — container won't boot | Med (self-verify exists) | **S** |
| 7 | **Dockerfile lints** A3/B3/RT-04 (pip target, build-in-CI) | #4 | Med | Low | **S** |
| 8 | **Logging sentinel** E1/O6/RT-08 | #8 | Med — blind ops | Low | **S** |
| 9 | **CSRF unit + probe** C2/O5/RT-05 | #5 | Med (now fixed) | Med | **S** |
| 10 | **Fresh-boot integrity** O3/RT-10 | #10 | Med — first-run only | Low | **M** (needs staging) |

Effort: **S** ≈ ≤½ day, **M** ≈ 1–2 days.

---

## 6. Tooling Recommendations (minimal, fits the existing stack)

The stack already has **pytest** (implied by `pyproject` dev extras), **TypeScript +
Vite**, **Docker**, and **Dockhand**. Add the *minimum* to close the biggest gaps:

1. **`pytest` + `responses` (or `requests-mock`)** — for the Ollama provider error-path
   tests (E2) and any HTTP-dependent unit. No real Ollama in CI. *(new dev dep: small)*

2. **`Vitest`** for the frontend — currently there is no JS test runner. Vitest is the
   native Vite companion, zero extra build config. Covers C2/C3 (CSRF header, non-JSON
   tolerance) and the contract typecheck. *(new dev dep)*

3. **API contract testing — the priority recommendation.** This boundary caused #5 and
   #9 and will keep causing bugs while two hand-written interfaces face each other.
   Establish **one source of truth and generate the rest:**
   - Define the sidecar response shapes as **Pydantic models** (you already return
     plain dicts; wrapping the `/status` and `/ingestion` responses in Pydantic is a
     small change and *also* removes the fragile hand-mapping in
     `IngestionRunRepository.get_latest`).
   - Emit **JSON Schema** from those models in CI (`Model.model_json_schema()`).
   - Generate the TS interfaces from that schema with
     **`json-schema-to-typescript`**, replacing the hand-written
     `types/status.ts` / `types/api.ts`. Drift becomes a **compile error**, not a
     production 500.
   - Cheaper interim if Pydantic adoption is deferred: a **shared JSON fixture**
     captured by the Python contract test (C1) and type-checked on the TS side (C2
     fixture import). This catches key drift today with near-zero new tooling.

   *Recommended end state:* Pydantic → JSON Schema → `json-schema-to-typescript`, run in
   CI so the generated `types/*.ts` is verified clean (`git diff --exit-code`).

4. **`hadolint`** (optional) for Dockerfile linting, or keep the tiny pytest greps
   (B3/A3) if you'd rather not add a binary. The pytest approach is lower-friction and
   already runs in the same job.

5. **No new CD tooling.** #2 is solved with a `LABEL` + an `inspect` assertion in the
   existing Dockhand deploy step — do **not** add a heavier release system.

### Untestable-as-written — minimal refactors required
- **Scheduler start** (`app.py`) is inferred from `app_env`; add
  `config.scheduler_enabled` so tests can construct the app without launching scans.
- **Pipeline factories** (`pipeline._do_run`) hard-call `get_embedding_provider` /
  `get_vector_store`; let `run_pipeline_once` accept injected `provider`/`store` so
  D1/D2/RT-07 are clean unit tests.
- **`httpClient.ts`** calls `response.json()` unconditionally; wrap in try/catch and
  return a structured error (closes C3 and makes the client robust to any future HTML
  error page).
- **`get_latest` hand-mapping** is the live instance of the #9 pattern; folding it into a
  Pydantic model (rec. #3) removes the class of bug, not just this case.
