from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS books_ai (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id         INTEGER NOT NULL UNIQUE,
    title                   TEXT NOT NULL,
    author_sort             TEXT,
    authors_json            TEXT NOT NULL DEFAULT '[]',
    tags_json               TEXT NOT NULL DEFAULT '[]',
    series_name             TEXT,
    language                TEXT,
    calibre_path            TEXT NOT NULL,
    cover_relative_path     TEXT,
    metadata_hash           TEXT NOT NULL,
    formats_hash            TEXT NOT NULL DEFAULT '',
    last_calibre_timestamp  TEXT,
    last_seen_at            TEXT NOT NULL,
    indexed_at              TEXT,
    ingestion_status        TEXT NOT NULL DEFAULT 'pending',
    ingestion_error         TEXT,
    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS book_formats_ai (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id     INTEGER NOT NULL,
    format              TEXT NOT NULL,
    relative_path       TEXT NOT NULL,
    file_size_bytes     INTEGER,
    mtime_ns            INTEGER,
    sha256              TEXT,
    extracted_at        TEXT,
    extraction_status   TEXT NOT NULL DEFAULT 'pending',
    extraction_error    TEXT,
    UNIQUE(calibre_book_id, format),
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id INTEGER NOT NULL,
    chunk_uid       TEXT NOT NULL UNIQUE,
    source_type     TEXT NOT NULL,
    source_format   TEXT,
    chunk_index     INTEGER NOT NULL,
    heading         TEXT,
    text            TEXT NOT NULL,
    token_estimate  INTEGER NOT NULL,
    char_start      INTEGER,
    char_end        INTEGER,
    embedding_model TEXT,
    vector_id       TEXT,
    embedded_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_concepts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_slug    TEXT NOT NULL UNIQUE,
    label           TEXT NOT NULL,
    description     TEXT,
    concept_type    TEXT NOT NULL,
    created_by      TEXT NOT NULL DEFAULT 'system',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS book_concepts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id     INTEGER NOT NULL,
    concept_slug        TEXT NOT NULL,
    confidence          REAL NOT NULL,
    evidence_chunk_uid  TEXT,
    rationale           TEXT,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(calibre_book_id, concept_slug),
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE,
    FOREIGN KEY(concept_slug)    REFERENCES ai_concepts(concept_slug) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS curated_collections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_slug     TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    collection_type     TEXT NOT NULL,
    generation_prompt   TEXT,
    refresh_policy      TEXT NOT NULL DEFAULT 'manual',
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS curated_collection_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_slug     TEXT NOT NULL,
    calibre_book_id     INTEGER NOT NULL,
    rank                INTEGER NOT NULL,
    score               REAL NOT NULL,
    match_reason        TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_slug, calibre_book_id),
    FOREIGN KEY(collection_slug) REFERENCES curated_collections(collection_slug) ON DELETE CASCADE,
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendation_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key        TEXT NOT NULL,
    calibre_book_id INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    event_weight    REAL NOT NULL DEFAULT 1.0,
    occurred_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     TEXT,
    status          TEXT NOT NULL,
    scanned_books   INTEGER NOT NULL DEFAULT 0,
    changed_books   INTEGER NOT NULL DEFAULT 0,
    embedded_chunks INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0
);

-- ── Metadata enrichment (Feature 4) ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS enrichment_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id INTEGER NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'queued',   -- queued|processing|done|error
    error           TEXT,
    queued_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrichment_suggestions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id         INTEGER NOT NULL UNIQUE,
    suggested_tags_json     TEXT NOT NULL DEFAULT '[]',
    suggested_description   TEXT,
    suggested_reading_level TEXT,
    suggested_series_name   TEXT,
    suggested_series_index  REAL,
    confidence              REAL,
    chat_model              TEXT,
    review_status           TEXT NOT NULL DEFAULT 'pending',  -- pending|reviewed|dismissed
    generated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrichment_reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    calibre_book_id     INTEGER NOT NULL,
    applied_tags_json   TEXT,                 -- NULL when the tags field was rejected
    applied_description TEXT,                 -- NULL when the blurb was rejected
    applied_reading_level TEXT,
    applied_series_name TEXT,
    applied_series_index REAL,
    decision_json       TEXT NOT NULL,        -- per-field accept/reject/edit record
    reviewer            TEXT NOT NULL DEFAULT 'admin',
    writeback_status    TEXT NOT NULL,        -- applied|failed
    writeback_error     TEXT,
    applied_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(calibre_book_id) REFERENCES books_ai(calibre_book_id) ON DELETE CASCADE
);

-- ── Chat provider rate limits (free-tier guard) ──────────────────────────────

CREATE TABLE IF NOT EXISTS provider_rate_limits (
    provider    TEXT PRIMARY KEY,           -- gemini|anthropic|openai|grok|meta|ollama
    rpm         INTEGER,                     -- max requests / rolling 60s (NULL = unlimited)
    rph         INTEGER,                     -- max requests / rolling 3600s (NULL = unlimited)
    enabled     INTEGER NOT NULL DEFAULT 1,  -- 0 = never use this provider
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_enrichment_queue_status
    ON enrichment_queue(status);

CREATE INDEX IF NOT EXISTS idx_enrichment_suggestions_review
    ON enrichment_suggestions(review_status);

CREATE INDEX IF NOT EXISTS idx_enrichment_reviews_book
    ON enrichment_reviews(calibre_book_id);

CREATE INDEX IF NOT EXISTS idx_books_ai_status
    ON books_ai(ingestion_status);

CREATE INDEX IF NOT EXISTS idx_book_chunks_book
    ON book_chunks(calibre_book_id);

CREATE INDEX IF NOT EXISTS idx_book_concepts_concept
    ON book_concepts(concept_slug);

CREATE INDEX IF NOT EXISTS idx_collection_items_slug_rank
    ON curated_collection_items(collection_slug, rank);

CREATE INDEX IF NOT EXISTS idx_rec_events_user
    ON recommendation_events(user_key);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
