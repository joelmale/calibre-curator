from __future__ import annotations

import hashlib
import json

from ..db.calibre_reader import CalibreBookRecord


def compute_metadata_hash(record: CalibreBookRecord) -> str:
    """Stable SHA-256 of the metadata fields we care about.

    Changing any of these fields causes the book to be re-indexed.
    File content is checked separately in the extraction phase (Phase 3).
    """
    payload = json.dumps({
        "title":        record.title,
        "author_sort":  record.author_sort,
        "authors":      record.authors,
        "tags":         record.tags,
        "series_name":  record.series_name,
        "language":     record.language,
        "last_modified": record.last_modified,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_formats_hash(record: CalibreBookRecord) -> str:
    """SHA-256 of format names and stored sizes — detects added/removed formats
    and size changes without hitting the filesystem."""
    payload = json.dumps(
        [
            {"format": f.format, "size": f.uncompressed_size}
            for f in sorted(record.format_details, key=lambda f: f.format)
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def detect_changed_books(
    calibre_records: list[CalibreBookRecord],
    known: dict[int, tuple[str, str]],
) -> tuple[list[CalibreBookRecord], set[int]]:
    """Compare Calibre records against the current sidecar index.

    Args:
        calibre_records: All books currently in Calibre.
        known: Mapping of calibre_book_id → (metadata_hash, formats_hash)
               from the sidecar DB.

    Returns:
        (changed_or_new, removed_ids) where:
          - changed_or_new: books that are new or whose hashes differ
          - removed_ids: IDs present in 'known' but absent from Calibre
    """
    current_ids = {r.book_id for r in calibre_records}
    removed_ids = set(known.keys()) - current_ids

    changed: list[CalibreBookRecord] = []
    for record in calibre_records:
        meta_hash = compute_metadata_hash(record)
        fmt_hash = compute_formats_hash(record)
        prev = known.get(record.book_id)
        if prev is None or prev != (meta_hash, fmt_hash):
            changed.append(record)

    return changed, removed_ids
