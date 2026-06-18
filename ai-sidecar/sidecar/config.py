from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    listen_host: str = field(default_factory=lambda: os.getenv("LISTEN_HOST", "0.0.0.0"))
    listen_port: int = field(default_factory=lambda: int(os.getenv("LISTEN_PORT", "8090")))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "production"))

    calibre_library_root: Path = field(
        default_factory=lambda: Path(os.getenv("CALIBRE_LIBRARY_ROOT", "/calibre-library"))
    )
    calibre_metadata_db: Path = field(
        default_factory=lambda: Path(os.getenv("CALIBRE_METADATA_DB", "/calibre-library/metadata.db"))
    )
    sidecar_db_path: Path = field(
        default_factory=lambda: Path(os.getenv("SIDECAR_DB_PATH", "/state/ai_sidecar.sqlite3"))
    )

    vector_backend: str = field(default_factory=lambda: os.getenv("VECTOR_BACKEND", "chroma"))
    chroma_persist_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CHROMA_PERSIST_DIR", "/state/chroma"))
    )

    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "ollama")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    )
    ollama_embed_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    )
    ollama_chat_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:latest")
    )

    openai_api_key: str | None = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY") or None
    )
    openai_embed_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    )

    shared_token: str = field(
        default_factory=lambda: os.getenv("AI_SIDECAR_SHARED_TOKEN", "")
    )
    scan_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("SCAN_INTERVAL_SECONDS", "300"))
    )
    max_extracted_chars_per_book: int = field(
        default_factory=lambda: int(os.getenv("MAX_EXTRACTED_CHARS_PER_BOOK", "120000"))
    )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
