from __future__ import annotations

import pytest

from sidecar.ingestion.chunker import Chunk, chunk_text


BOOK_ID = 42


class TestChunkTextEmpty:
    def test_empty_string_returns_no_chunks(self):
        assert chunk_text("", BOOK_ID) == []

    def test_whitespace_only_returns_no_chunks(self):
        assert chunk_text("   \n\n\t  ", BOOK_ID) == []


class TestChunkTextShortText:
    def test_short_text_produces_one_chunk(self):
        text = "This is a short passage that fits in a single chunk easily."
        chunks = chunk_text(text, BOOK_ID)
        assert len(chunks) == 1

    def test_single_chunk_contains_full_text(self):
        text = "The quick brown fox jumps over the lazy dog."
        chunks = chunk_text(text, BOOK_ID)
        assert chunks[0].text == text

    def test_chunk_has_correct_book_id_in_uid(self):
        chunks = chunk_text("Some text here.", BOOK_ID)
        # uid is deterministic — same book_id + index always gives same uid
        assert chunks[0].chunk_uid == chunk_text("Some text here.", BOOK_ID)[0].chunk_uid

    def test_different_book_ids_produce_different_uids(self):
        text = "Same text."
        uid_a = chunk_text(text, 1)[0].chunk_uid
        uid_b = chunk_text(text, 2)[0].chunk_uid
        assert uid_a != uid_b


class TestChunkTextLongText:
    def _long_prose(self, n_words: int) -> str:
        word = "bibliophile"
        return " ".join([word] * n_words)

    def test_long_text_produces_multiple_chunks(self):
        text = self._long_prose(2000)
        chunks = chunk_text(text, BOOK_ID, target_tokens=400)
        assert len(chunks) > 1

    def test_chunk_indices_are_sequential(self):
        text = self._long_prose(2000)
        chunks = chunk_text(text, BOOK_ID, target_tokens=400)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_chunk_uids_are_unique(self):
        text = self._long_prose(2000)
        chunks = chunk_text(text, BOOK_ID, target_tokens=400)
        uids = [c.chunk_uid for c in chunks]
        assert len(uids) == len(set(uids))

    def test_token_estimate_is_positive(self):
        text = self._long_prose(2000)
        for chunk in chunk_text(text, BOOK_ID, target_tokens=400):
            assert chunk.token_estimate > 0

    def test_char_positions_are_monotonic(self):
        text = self._long_prose(2000)
        chunks = chunk_text(text, BOOK_ID, target_tokens=400)
        for c in chunks:
            assert c.char_start < c.char_end


class TestChunkTextHeadings:
    CHAPTER_TEXT = (
        "Chapter 1\n"
        "In the beginning there was darkness and the void was empty.\n"
        "Many words followed as the story unfolded over many pages.\n\n"
        "Chapter 2\n"
        "The hero arrived at the castle gates and knocked loudly.\n"
        "She waited patiently for someone to answer her call.\n"
    )

    def test_heading_is_captured(self):
        chunks = chunk_text(self.CHAPTER_TEXT, BOOK_ID)
        headings = [c.heading for c in chunks if c.heading]
        assert any("Chapter" in h for h in headings)

    def test_chunks_from_different_chapters_have_different_headings(self):
        chunks = chunk_text(self.CHAPTER_TEXT, BOOK_ID)
        headings = {c.heading for c in chunks if c.heading}
        assert len(headings) >= 2

    def test_no_heading_chunk_allowed(self):
        # Text with no chapter markers should still produce chunks with heading=None
        text = "Just plain prose without any chapter markers." * 5
        chunks = chunk_text(text, BOOK_ID)
        assert all(c.heading is None for c in chunks)


class TestChunkDeterminism:
    def test_same_input_produces_same_chunks(self):
        text = "Deterministic chunking is important for cache invalidation." * 50
        a = chunk_text(text, BOOK_ID)
        b = chunk_text(text, BOOK_ID)
        assert [(c.chunk_uid, c.text) for c in a] == [(c.chunk_uid, c.text) for c in b]
