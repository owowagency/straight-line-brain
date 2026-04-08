from __future__ import annotations

import re


def _estimate_tokens(text: str) -> int:
    return len(text.split())


# ------------------------------------------------------------------
# Sentence-boundary helpers
# ------------------------------------------------------------------

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on `. `, `! `, `? ` boundaries."""
    parts = _SENTENCE_END.split(text)
    return [s.strip() for s in parts if s.strip()]


# ------------------------------------------------------------------
# Chunking strategies
# ------------------------------------------------------------------


def _chunk_single(content: str) -> list[str]:
    """Return full content as a single chunk. For short types like propositie, tone_of_voice."""
    content = content.strip()
    return [content] if content else []


def _chunk_by_sections(content: str) -> list[str]:
    """Split on markdown headers, preserving each header with its section body.

    Every chunk keeps its section header so the embedding captures the context
    of *what* the section is about (e.g. "## Diensten\\n...").
    """
    # Split *before* markdown headers, keeping the header with its body
    parts = re.split(r"\n(?=#{1,3}\s+)", content)

    # If no headers found, try double newlines
    if len(parts) <= 1:
        parts = re.split(r"\n\n+", content)

    chunks = [p.strip() for p in parts if p.strip()]

    # If still only one chunk and it's long, fall back to sliding window
    if len(chunks) <= 1 and _estimate_tokens(content) > 500:
        return _chunk_sliding_window(content)

    # For sections that are too long, sub-chunk with sliding window
    # while prepending the section header for context
    final: list[str] = []
    for chunk in chunks:
        if _estimate_tokens(chunk) > 600:
            # Extract header line if present
            lines = chunk.split("\n", 1)
            if len(lines) == 2 and lines[0].startswith("#"):
                header = lines[0]
                body = lines[1]
                sub_chunks = _chunk_sliding_window(body)
                for sc in sub_chunks:
                    final.append(f"{header}\n\n{sc}")
            else:
                final.extend(_chunk_sliding_window(chunk))
        else:
            final.append(chunk)

    return final if final else [content.strip()]


def _chunk_sliding_window(
    content: str, window_size: int = 400, overlap: int = 50
) -> list[str]:
    """Sliding window chunking that respects sentence boundaries.

    Instead of cutting mid-sentence at fixed word counts, this groups
    whole sentences until the window fills up, then starts a new chunk
    with *overlap* words of trailing context from the previous chunk.
    """
    sentences = _split_sentences(content)
    if not sentences:
        return [content.strip()] if content.strip() else []

    # If the whole text fits in one window, return as-is
    if _estimate_tokens(content) <= window_size:
        return [content.strip()]

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        s_tokens = _estimate_tokens(sentence)

        if current_tokens + s_tokens > window_size and current_sentences:
            # Emit current chunk
            chunks.append(" ".join(current_sentences))

            # Build overlap from the tail of emitted sentences
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                t = _estimate_tokens(s)
                if overlap_tokens + t > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += t

            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append(sentence)
        current_tokens += s_tokens

    # Emit remaining
    if current_sentences:
        remaining = " ".join(current_sentences)
        # Avoid duplicating the last chunk
        if not chunks or remaining != chunks[-1]:
            chunks.append(remaining)

    return chunks


# Strategy dispatch by knowledge entry type
_STRATEGIES = {
    "propositie": _chunk_single,
    "tone_of_voice": _chunk_single,
    "bedrijfsprofiel": _chunk_single,
    "brand": _chunk_single,
    "inzicht": _chunk_single,
    "dienst": _chunk_by_sections,
    "icp": _chunk_by_sections,
    "werkwijze": _chunk_by_sections,
    "synthese": _chunk_by_sections,
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
