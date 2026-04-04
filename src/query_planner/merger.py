"""
Result merger: combines structured + semantic query results.

Strategies:
- "structured_first": Numbers as basis, semantic context alongside
- "semantic_first": Qualitative insights first, backed by data
- "interleaved": Alternating numbers and context
"""

from __future__ import annotations

from src.schemas.retrieval import SemanticChunkResult


class ResultMerger:
    def merge(
        self,
        strategy: str,
        structured_results: list[dict] | None = None,
        semantic_results: list[SemanticChunkResult] | None = None,
        aggregation: dict | None = None,
    ) -> dict:
        """Merge structured and semantic results based on strategy."""
        structured_results = structured_results or []
        semantic_results = semantic_results or []

        if strategy == "structured_first":
            return self._structured_first(structured_results, semantic_results, aggregation)
        elif strategy == "semantic_first":
            return self._semantic_first(structured_results, semantic_results, aggregation)
        elif strategy == "interleaved":
            return self._interleaved(structured_results, semantic_results, aggregation)
        else:
            return self._semantic_first(structured_results, semantic_results, aggregation)

    def _structured_first(
        self,
        structured: list[dict],
        semantic: list[SemanticChunkResult],
        aggregation: dict | None,
    ) -> dict:
        return {
            "primary": "structured",
            "structured_data": {
                "records": structured,
                "aggregation": aggregation,
                "count": len(structured),
            },
            "semantic_context": [
                {"title": r.entry_title, "content": r.content, "score": r.score}
                for r in semantic[:3]
            ],
        }

    def _semantic_first(
        self,
        structured: list[dict],
        semantic: list[SemanticChunkResult],
        aggregation: dict | None,
    ) -> dict:
        return {
            "primary": "semantic",
            "semantic_results": [
                {
                    "title": r.entry_title,
                    "type": r.entry_type,
                    "content": r.content,
                    "score": r.score,
                }
                for r in semantic
            ],
            "supporting_data": {
                "records": structured[:5] if structured else None,
                "aggregation": aggregation,
            },
        }

    def _interleaved(
        self,
        structured: list[dict],
        semantic: list[SemanticChunkResult],
        aggregation: dict | None,
    ) -> dict:
        combined = []
        sem_iter = iter(semantic)
        str_iter = iter(structured)

        for _ in range(max(len(structured), len(semantic))):
            try:
                s = next(str_iter)
                combined.append({"type": "data", "record": s})
            except StopIteration:
                pass
            try:
                r = next(sem_iter)
                combined.append({
                    "type": "context",
                    "title": r.entry_title,
                    "content": r.content,
                    "score": r.score,
                })
            except StopIteration:
                pass

        return {
            "primary": "interleaved",
            "combined": combined,
            "aggregation": aggregation,
        }
