"""
QueryPlanner: classifies free-form queries and routes them to the right data layer(s).

Two modes:
1. Rule-based (fast, cheap) for known patterns — confidence > 0.85
2. Fallback to rule-based with lower threshold (LLM-based planned for future)

The planner returns a QueryPlan that the brain endpoint uses to:
- Route to narrow endpoints (direct DB lookups)
- Run structured queries (SQL on analytics_data)
- Run semantic queries (vector search on knowledge_chunks)
- Run both in parallel and merge results
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import AnalyticsRecord, KnowledgeChunk, KnowledgeEntry
from src.embeddings.service import EmbeddingService
from src.query_planner.merger import ResultMerger
from src.query_planner.rules import QueryPlan, RuleBasedClassifier
from src.schemas.retrieval import SemanticChunkResult

logger = logging.getLogger(__name__)


class QueryPlanner:
    def __init__(self) -> None:
        self.rules = RuleBasedClassifier()
        self.merger = ResultMerger()

    async def plan(self, query: str) -> QueryPlan:
        """Classify a free-form query into a QueryPlan."""
        return self.rules.classify(query)

    async def execute(
        self,
        plan: QueryPlan,
        query: str,
        session: AsyncSession,
        embedder: EmbeddingService,
    ) -> dict:
        """Execute a QueryPlan and return merged results."""

        # If plan routes to a narrow endpoint, use direct lookup
        if plan.narrow_type:
            results = await self._execute_narrow(plan, session)
            return {
                "strategy": f"narrow_{plan.narrow_type}",
                "results": results,
                "merged": None,
            }

        # Execute based on intent
        if plan.intent == "structured":
            structured, agg = await self._execute_structured(query, session)
            return {
                "strategy": "structured",
                "results": [],
                "merged": self.merger.merge(
                    plan.merge_strategy,
                    structured_results=structured,
                    aggregation=agg,
                ),
            }

        elif plan.intent == "semantic":
            results = await self._execute_semantic(query, session, embedder)
            return {
                "strategy": "semantic",
                "results": results,
                "merged": None,
            }

        elif plan.intent == "both":
            # Run structured + semantic in parallel
            structured_task = self._execute_structured(query, session)
            semantic_task = self._execute_semantic(query, session, embedder)
            (structured, agg), semantic_results = await asyncio.gather(
                structured_task, semantic_task
            )
            merged = self.merger.merge(
                plan.merge_strategy,
                structured_results=structured,
                semantic_results=semantic_results,
                aggregation=agg,
            )
            return {
                "strategy": "both",
                "results": semantic_results,
                "merged": merged,
            }

        # Fallback
        results = await self._execute_semantic(query, session, embedder)
        return {
            "strategy": "semantic_fallback",
            "results": results,
            "merged": None,
        }

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    async def _execute_narrow(
        self, plan: QueryPlan, session: AsyncSession
    ) -> list[SemanticChunkResult]:
        """Direct DB lookup for narrow endpoints."""
        type_map = {
            "icp": ["icp"],
            "tone_of_voice": ["tone_of_voice"],
            "company": ["bedrijfsprofiel", "propositie"],
            "services": ["dienst"],
        }
        entry_types = type_map.get(plan.narrow_type, [])

        q = (
            select(KnowledgeEntry)
            .where(KnowledgeEntry.type.in_(entry_types), KnowledgeEntry.is_active.is_(True))
            .options(selectinload(KnowledgeEntry.chunks))
        )

        # Apply segment filter for ICP and services
        if plan.narrow_params and plan.narrow_params.get("segment"):
            segment = plan.narrow_params["segment"]
            if plan.narrow_type == "icp":
                q = q.where(KnowledgeEntry.title.ilike(f"%{segment}%"))
            elif plan.narrow_type == "services":
                q = q.where(KnowledgeEntry.content.ilike(f"%{segment}%"))

        result = await session.execute(q)
        entries = result.scalars().all()

        results = []
        for entry in entries:
            for chunk in sorted(entry.chunks, key=lambda c: c.chunk_index):
                results.append(
                    SemanticChunkResult(
                        chunk_id=chunk.id,
                        entry_id=entry.id,
                        entry_title=entry.title,
                        entry_type=entry.type,
                        content=chunk.content,
                        score=1.0,
                        metadata=chunk.metadata_,
                    )
                )
        return results

    async def _execute_semantic(
        self,
        query: str,
        session: AsyncSession,
        embedder: EmbeddingService,
        top_k: int = 5,
    ) -> list[SemanticChunkResult]:
        """Vector similarity search with instruction-aware embedding,
        entry deduplication, and score threshold."""
        _MIN_SCORE = 0.3
        _OVERFETCH = 3

        # Use instruction-aware query embedding for better retrieval
        query_embedding = await embedder.embed_query(query)
        distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)

        q = (
            select(
                KnowledgeChunk,
                KnowledgeEntry.title.label("entry_title"),
                KnowledgeEntry.type.label("entry_type"),
                distance.label("distance"),
            )
            .join(KnowledgeEntry, KnowledgeChunk.entry_id == KnowledgeEntry.id)
            .where(KnowledgeEntry.is_active.is_(True))
            .where(KnowledgeChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k * _OVERFETCH)
        )
        result = await session.execute(q)
        rows = result.all()

        # Deduplicate: keep only the best chunk per entry, drop noise
        seen_entries: set[str] = set()
        results: list[SemanticChunkResult] = []
        for row in rows:
            score = round(1.0 - row.distance, 4)
            if score < _MIN_SCORE:
                continue
            entry_id_str = str(row.KnowledgeChunk.entry_id)
            if entry_id_str in seen_entries:
                continue
            seen_entries.add(entry_id_str)
            results.append(
                SemanticChunkResult(
                    chunk_id=row.KnowledgeChunk.id,
                    entry_id=row.KnowledgeChunk.entry_id,
                    entry_title=row.entry_title,
                    entry_type=row.entry_type,
                    content=row.KnowledgeChunk.content,
                    score=score,
                    metadata=row.KnowledgeChunk.metadata_,
                )
            )
            if len(results) >= top_k:
                break

        return results

    async def _execute_structured(
        self, query: str, session: AsyncSession
    ) -> tuple[list[dict], dict | None]:
        """Query analytics data. Infers metric_type from query text."""
        # Simple metric type inference from query
        q_lower = query.lower()
        metric_type = "deal"  # default
        for mt in ["deal", "revenue", "omzet", "conversie", "pipeline"]:
            if mt in q_lower:
                metric_type = mt
                break

        base_filter = [AnalyticsRecord.metric_type == metric_type]

        records_q = (
            select(AnalyticsRecord)
            .where(*base_filter)
            .order_by(AnalyticsRecord.period_start)
            .limit(50)
        )
        result = await session.execute(records_q)
        records = result.scalars().all()

        # Aggregation
        agg_q = select(
            func.sum(AnalyticsRecord.value).label("total"),
            func.avg(AnalyticsRecord.value).label("average"),
            func.count(AnalyticsRecord.id).label("count"),
        ).where(*base_filter)
        agg_result = await session.execute(agg_q)
        agg_row = agg_result.one()

        record_dicts = [
            {
                "source": r.source,
                "metric_type": r.metric_type,
                "dimensions": r.dimensions,
                "value": float(r.value),
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
            }
            for r in records
        ]

        aggregation = {
            "metric_type": metric_type,
            "total": float(agg_row.total) if agg_row.total else None,
            "average": float(agg_row.average) if agg_row.average else None,
            "count": agg_row.count,
        }

        return record_dicts, aggregation
