"""
Analyzes query_log for recurring patterns and generates endpoint proposals.

Runs on-demand via API call:
1. Groups queries by normalized form
2. Counts frequency per pattern
3. If frequency > threshold → generates endpoint proposal
4. Proposals go to the review queue (staging status)
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import QueryLog, RegisteredEndpoint
from src.schemas.registry import PatternDetectionResult

logger = logging.getLogger(__name__)

# Minimum occurrences to suggest a new endpoint
DEFAULT_THRESHOLD = 3
# Max days to look back
DEFAULT_LOOKBACK_DAYS = 30


def _normalize_query(query: str) -> str:
    """Normalize a query to detect patterns.

    - Lowercase
    - Remove specific values (dates, numbers, names)
    - Keep structural keywords
    """
    q = query.lower().strip()
    # Remove dates
    q = re.sub(r"\d{4}-\d{2}-\d{2}", "<date>", q)
    # Remove numbers
    q = re.sub(r"\b\d+([.,]\d+)?\b", "<num>", q)
    # Remove quoted strings
    q = re.sub(r"[\"'].*?[\"']", "<val>", q)
    # Collapse whitespace
    q = re.sub(r"\s+", " ", q)
    return q


class PatternDetector:
    async def detect_patterns(
        self,
        session: AsyncSession,
        threshold: int = DEFAULT_THRESHOLD,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> list[PatternDetectionResult]:
        """Analyze recent queries and find recurring patterns."""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Fetch recent queries (brain/query and semantic/search are most interesting)
        query = (
            select(QueryLog)
            .where(
                QueryLog.created_at >= cutoff,
                QueryLog.endpoint_used.in_(["brain/query", "semantic/search"]),
            )
            .order_by(QueryLog.created_at.desc())
            .limit(1000)
        )
        result = await session.execute(query)
        logs = result.scalars().all()

        if not logs:
            return []

        # Normalize and count patterns
        pattern_queries: dict[str, list[str]] = {}
        for log in logs:
            normalized = _normalize_query(log.query_text)
            if normalized not in pattern_queries:
                pattern_queries[normalized] = []
            pattern_queries[normalized].append(log.query_text)

        # Filter by threshold
        patterns = []
        for normalized, queries in pattern_queries.items():
            if len(queries) >= threshold:
                # Check if we already have a registered endpoint for this pattern
                existing = await session.execute(
                    select(RegisteredEndpoint).where(
                        RegisteredEndpoint.query_template.ilike(f"%{normalized[:50]}%")
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                suggested_name = self._suggest_name(normalized)
                patterns.append(
                    PatternDetectionResult(
                        pattern=normalized,
                        frequency=len(queries),
                        sample_queries=queries[:5],
                        suggested_name=suggested_name,
                        suggested_template=self._suggest_template(normalized, queries[0]),
                    )
                )

        # Sort by frequency (most common first)
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns

    def _suggest_name(self, normalized: str) -> str:
        """Generate a suggested endpoint name from a normalized pattern."""
        # Take first few meaningful words
        words = [w for w in normalized.split() if w not in {"<date>", "<num>", "<val>", "?", "de", "het", "een", "van", "voor", "bij", "in", "op"}]
        name = "_".join(words[:4])
        # Clean up
        name = re.sub(r"[^a-z0-9_]", "", name)
        return name or "custom_query"

    def _suggest_template(self, normalized: str, sample: str) -> str:
        """Generate a query template from the pattern."""
        # Replace normalized placeholders with parameter markers
        template = normalized
        template = template.replace("<date>", "{date}")
        template = template.replace("<num>", "{value}")
        template = template.replace("<val>", "{param}")
        return template
