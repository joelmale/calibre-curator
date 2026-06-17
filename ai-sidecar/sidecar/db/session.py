from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Generator

from ..config import get_config


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    config = get_config()
    conn = sqlite3.connect(str(config.sidecar_db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
