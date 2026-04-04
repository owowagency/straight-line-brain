from __future__ import annotations

import re


def _estimate_tokens(text: str) -> int:
    return len(text.split())


def _chunk_single(content: str) -> list[str]:
    """Return full content as a single chunk. For short types like propositie, tone_of_voice."""
    content = content.strip()
    return [content] if content else []


def _chunk_by_sections(content: str) -> list[str]:
    """Split on markdown headers or double newlines. For dienst, icp, werkwijze."""
    # Try splitting on markdown headers first
    parts = re.split(r"\n(?=#{1,3}\s+)", content)

    # If only one part, try double newlines
    if len(parts) <= 1:
        parts = re.split(r"\n\n+", content)

    chunks = [p.strip() for p in parts if p.strip()]

    # If still only one chunk and it's long, fall back to sliding window
    if len(chunks) <= 1 and _estimate_tokens(content) > 500:
        return _chunk_sliding_window(content)

    return chunks if chunks else [content.strip()]


def _chunk_sliding_window(
    content: str, window_size: int = 400, overlap: int = 50
) -> list[str]:
    """Sliding window chunking with word-level overlap."""
    words = content.split()
    if len(words) <= window_size:
        return [content.strip()]

    chunks = []
    start = 0
    while start < len(words):
        end = start + window_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap

    return chunks


# Strategy dispatch by knowledge entry type
_STRATEGIES = {
    "propositie": _chunk_single,
    "tone_of_voice": _chunk_single,
    "bedrijfsprofiel": _chunk_single,
    "brand": _chunk_single,
    "dienst": _chunk_by_sections,
    "icp": _chunk_by_sections,
    "werkwijze": _chunk_by_sections,
}


class ChunkingService:
    def chunk(self, entry_type: str, content: str) -> list[str]:
        strategy = _STRATEGIES.get(entry_type, _chunk_sliding_window)
        return strategy(content)

    def chunk_with_token_counts(
        self, entry_type: str, content: str
    ) -> list[tuple[str, int]]:
        chunks = self.chunk(entry_type, content)
        return [(c, _estimate_tokens(c)) for c in chunks]
