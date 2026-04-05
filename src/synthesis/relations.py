"""
RelationDetector: automatically detects related knowledge entries
using embedding similarity and updates cross-references in metadata.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeEntry

logger = logging.getLogger(__name__)


class RelationDetector:
    async def detect_related(
        self,
        session: AsyncSession,
        entry_id: UUID,
        top_k: int = 5,
    ) -> list[dict]:
        """Find entries most similar to the given entry using embedding similarity."""
        entry = await session.get(KnowledgeEntry, entry_id)
        if entry is None or entry.embedding is None:
            return []

        distance = KnowledgeEntry.embedding.cosine_distance(entry.embedding)
        query = (
            select(
                KnowledgeEntry.id,
                KnowledgeEntry.title,
                KnowledgeEntry.type,
                distance.label("distance"),
            )
            .where(
                KnowledgeEntry.is_active.is_(True),
                KnowledgeEntry.id != entry_id,
                KnowledgeEntry.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(top_k)
        )
        result = await session.execute(query)
        rows = result.all()

        return [
            {
                "id": str(row.id),
                "title": row.title,
                "type": row.type,
                "score": round(1.0 - row.distance, 4),
            }
            for row in rows
        ]

    async def update_entry_relations(
        self,
        session: AsyncSession,
        entry_id: UUID,
        relations: list[dict],
    ) -> None:
        """Store detected relations in the entry's metadata."""
        entry = await session.get(KnowledgeEntry, entry_id)
        if entry is None:
            return

        metadata = dict(entry.metadata_) if entry.metadata_ else {}
        metadata["related_entries"] = relations
        entry.metadata_ = metadata

        # Also update the reverse direction on related entries
        for rel in relations:
            related = await session.get(KnowledgeEntry, UUID(rel["id"]))
            if related is None:
                continue
            rel_meta = dict(related.metadata_) if related.metadata_ else {}
            existing = rel_meta.get("related_entries", [])
            # Add back-reference if not already present
            entry_ref = {
                "id": str(entry_id),
                "title": entry.title,
                "type": entry.type,
                "score": rel["score"],
            }
            if not any(r["id"] == str(entry_id) for r in existing):
                existing.append(entry_ref)
                rel_meta["related_entries"] = existing
                related.metadata_ = rel_meta

        logger.info(
            "Updated relations for '%s': %d related entries",
            entry.title,
            len(relations),
        )
