from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# ~4 characters per token is a reasonable approximation for English prose
_CHARS_PER_TOKEN = 4

# Chapter heading patterns (matches "Chapter 1", "CHAPTER ONE", "Part II", etc.)
_HEADING_RE = re.compile(
    r"^(?:chapter|part|section|book|prologue|epilogue|introduction|conclusion)"
    r"[\s\w\-]*$",
    re.IGNORECASE,
)

# Minimum characters to bother emitting a chunk
_MIN_CHUNK_CHARS = 10


@dataclass(frozen=True)
class Chunk:
    chunk_uid: str       # deterministic: sha256(book_id + chunk_index)
    chunk_index: int
    heading: str | None
    text: str
    token_estimate: int
    char_start: int
    char_end: int


def _token_estimate(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _make_uid(calibre_book_id: int, chunk_index: int) -> str:
    raw = f"{calibre_book_id}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Chapter-aware splitting
# ---------------------------------------------------------------------------

def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    """Split text into (heading, body) sections on chapter-like lines."""
    lines = text.splitlines()
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and _HEADING_RE.match(stripped):
            if current_lines:
                body = " ".join(current_lines).strip()
                if body:
                    sections.append((current_heading, body))
            current_heading = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        body = " ".join(current_lines).strip()
        if body:
            sections.append((current_heading, body))

    return sections


# ---------------------------------------------------------------------------
# Sliding window fallback
# ---------------------------------------------------------------------------

def _sliding_window(
    text: str,
    heading: str | None,
    target_chars: int,
    overlap_chars: int,
    calibre_book_id: int,
    start_index: int,
    char_offset: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    pos = 0
    idx = start_index

    while pos < len(text):
        end = min(pos + target_chars, len(text))

        # Snap to sentence boundary within 200 chars of target
        if end < len(text):
            snap = text.rfind(". ", pos, end + 200)
            if snap != -1 and snap > pos + target_chars // 2:
                end = snap + 1

        chunk_text = text[pos:end].strip()
        if len(chunk_text) >= _MIN_CHUNK_CHARS:
            chunks.append(Chunk(
                chunk_uid=_make_uid(calibre_book_id, idx),
                chunk_index=idx,
                heading=heading,
                text=chunk_text,
                token_estimate=_token_estimate(chunk_text),
                char_start=char_offset + pos,
                char_end=char_offset + end,
            ))
            idx += 1

        pos = end - overlap_chars if end < len(text) else end

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    calibre_book_id: int,
    target_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Split extracted text into overlapping chunks suitable for embedding.

    Strategy:
    1. Split on chapter/part headings — each section becomes its own chunk
       stream, preserving the heading as context.
    2. Within each section, use a sliding window with sentence-boundary snapping
       so chunks don't cut mid-sentence.
    3. Sections short enough to fit in one chunk are emitted as-is.

    Args:
        text: Extracted book text.
        calibre_book_id: Used to generate deterministic chunk UIDs.
        target_tokens: Approximate token count per chunk.
        overlap_tokens: Overlap between adjacent chunks in the same section.
    """
    if not text.strip():
        return []

    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    sections = _split_by_headings(text)
    if not sections:
        sections = [(None, text)]

    all_chunks: list[Chunk] = []
    char_offset = 0

    for heading, body in sections:
        if len(body) <= target_chars:
            # Whole section fits in one chunk
            body = body.strip()
            if len(body) >= _MIN_CHUNK_CHARS:
                idx = len(all_chunks)
                all_chunks.append(Chunk(
                    chunk_uid=_make_uid(calibre_book_id, idx),
                    chunk_index=idx,
                    heading=heading,
                    text=body,
                    token_estimate=_token_estimate(body),
                    char_start=char_offset,
                    char_end=char_offset + len(body),
                ))
        else:
            new_chunks = _sliding_window(
                body, heading, target_chars, overlap_chars,
                calibre_book_id, len(all_chunks), char_offset,
            )
            all_chunks.extend(new_chunks)

        char_offset += len(body)

    return all_chunks
