"""
SynthesisGenerator: auto-generates synthesis documents when knowledge changes.

Triggers:
- New/updated ICP → "Segment Vergelijking"
- New/updated dienst → "Diensten Overzicht"

Synthesis documents are regular KnowledgeEntry records with type="synthese"
and auto_generated=true in metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChangeLog, KnowledgeChunk, KnowledgeEntry
from src.embeddings.chunking import ChunkingService
from src.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

# Which entry types trigger which synthesis documents
TRIGGERS = {
    "icp": ["segment_comparison"],
    "dienst": ["service_overview"],
    "propositie": ["company_overview"],
    "bedrijfsprofiel": ["company_overview"],
}

chunker = ChunkingService()


class SynthesisGenerator:
    def should_generate(self, entry_type: str) -> list[str]:
        """Determine which synthesis documents should be updated for this entry type."""
        return TRIGGERS.get(entry_type, [])

    async def generate(
        self,
        synthesis_type: str,
        session: AsyncSession,
        embedder: EmbeddingService,
    ) -> KnowledgeEntry | None:
        """Generate or update a synthesis document."""
        generators = {
            "segment_comparison": self._generate_segment_comparison,
            "service_overview": self._generate_service_overview,
            "company_overview": self._generate_company_overview,
        }
        gen_func = generators.get(synthesis_type)
        if gen_func is None:
            logger.warning("Unknown synthesis type: %s", synthesis_type)
            return None

        return await gen_func(session, embedder)

    async def _generate_segment_comparison(
        self, session: AsyncSession, embedder: EmbeddingService
    ) -> KnowledgeEntry:
        """Generate a comparison of all ICP segments."""
        icps = await self._fetch_entries_by_type(session, "icp")

        lines = [
            "# Segment Vergelijking",
            "",
            f"*Automatisch gegenereerd op basis van {len(icps)} klantprofielen.*",
            "",
        ]

        for icp in icps:
            lines.append(f"## {icp.title}")
            # Extract first ~200 chars as summary
            summary = icp.content[:200].rsplit(" ", 1)[0] + "..."
            lines.append(summary)
            lines.append("")

        if len(icps) >= 2:
            lines.append("## Vergelijking")
            lines.append("")
            lines.append("| Aspect | " + " | ".join(i.title.replace("ICP — ", "") for i in icps) + " |")
            lines.append("|--------|" + "|".join("-----" for _ in icps) + "|")
            lines.append("| Type | " + " | ".join(i.type for i in icps) + " |")
            lines.append("| Fragmenten | " + " | ".join(str(len(i.chunks)) for i in icps) + " |")
            lines.append("")

        content = "\n".join(lines)
        source_ids = [str(i.id) for i in icps]
        return await self._upsert_synthesis(
            session, embedder, "segment_comparison",
            "Segment Vergelijking", content, source_ids,
        )

    async def _generate_service_overview(
        self, session: AsyncSession, embedder: EmbeddingService
    ) -> KnowledgeEntry:
        """Generate an overview of all services."""
        services = await self._fetch_entries_by_type(session, "dienst")

        lines = [
            "# Diensten Overzicht",
            "",
            f"*Automatisch gegenereerd op basis van {len(services)} diensten.*",
            "",
        ]

        for svc in services:
            lines.append(f"## {svc.title}")
            summary = svc.content[:200].rsplit(" ", 1)[0] + "..."
            lines.append(summary)
            lines.append("")

        content = "\n".join(lines)
        source_ids = [str(s.id) for s in services]
        return await self._upsert_synthesis(
            session, embedder, "service_overview",
            "Diensten Overzicht", content, source_ids,
        )

    async def _generate_company_overview(
        self, session: AsyncSession, embedder: EmbeddingService
    ) -> KnowledgeEntry:
        """Generate a company overview from bedrijfsprofiel + propositie."""
        entries = await self._fetch_entries_by_type(session, "bedrijfsprofiel")
        entries += await self._fetch_entries_by_type(session, "propositie")

        lines = [
            "# Bedrijfsoverzicht",
            "",
            f"*Automatisch gegenereerd op basis van {len(entries)} bronnen.*",
            "",
        ]

        for entry in entries:
            lines.append(f"## {entry.title}")
            lines.append(entry.content)
            lines.append("")

        content = "\n".join(lines)
        source_ids = [str(e.id) for e in entries]
        return await self._upsert_synthesis(
            session, embedder, "company_overview",
            "Bedrijfsoverzicht", content, source_ids,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_entries_by_type(
        self, session: AsyncSession, entry_type: str
    ) -> list[KnowledgeEntry]:
        from sqlalchemy.orm import selectinload

        query = (
            select(KnowledgeEntry)
            .where(KnowledgeEntry.type == entry_type, KnowledgeEntry.is_active.is_(True))
            .options(selectinload(KnowledgeEntry.chunks))
            .order_by(KnowledgeEntry.title)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def _upsert_synthesis(
        self,
        session: AsyncSession,
        embedder: EmbeddingService,
        synthesis_type: str,
        title: str,
        content: str,
        source_entry_ids: list[str],
    ) -> KnowledgeEntry:
        """Create or update a synthesis entry."""
        # Find existing synthesis of this type
        query = select(KnowledgeEntry).where(
            KnowledgeEntry.type == "synthese",
            KnowledgeEntry.is_active.is_(True),
            KnowledgeEntry.metadata_["synthesis_type"].astext == synthesis_type,
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        metadata = {
            "auto_generated": True,
            "synthesis_type": synthesis_type,
            "source_entries": source_entry_ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing:
            existing.title = title
            existing.content = content
            existing.metadata_ = metadata
            existing.embedding = await embedder.embed_text(f"{title}\n\n{content}")
            # Re-chunk
            for chunk in list(existing.chunks):
                await session.delete(chunk)
            await self._create_chunks(session, embedder, existing, content, metadata)
            # Log changelog
            session.add(KnowledgeChangeLog(
                entry_id=existing.id,
                action="synthesis_updated",
                entry_title=title,
                entry_type="synthese",
                change_summary=f"Synthese '{synthesis_type}' bijgewerkt op basis van {len(source_entry_ids)} bronnen",
                triggered_by="synthesis_generator",
                metadata_={"synthesis_type": synthesis_type, "source_count": len(source_entry_ids)},
            ))
            logger.info("Updated synthesis: %s", title)
            return existing
        else:
            entry = KnowledgeEntry(
                type="synthese",
                title=title,
                content=content,
                created_by="synthesis_generator",
                metadata_=metadata,
                embedding=await embedder.embed_text(f"{title}\n\n{content}"),
            )
            session.add(entry)
            await session.flush()
            await self._create_chunks(session, embedder, entry, content, metadata)
            # Log changelog
            session.add(KnowledgeChangeLog(
                entry_id=entry.id,
                action="synthesis_created",
                entry_title=title,
                entry_type="synthese",
                change_summary=f"Synthese '{synthesis_type}' gegenereerd op basis van {len(source_entry_ids)} bronnen",
                triggered_by="synthesis_generator",
                metadata_={"synthesis_type": synthesis_type, "source_count": len(source_entry_ids)},
            ))
            logger.info("Created synthesis: %s", title)
            return entry

    async def _create_chunks(
        self,
        session: AsyncSession,
        embedder: EmbeddingService,
        entry: KnowledgeEntry,
        content: str,
        metadata: dict,
    ) -> None:
        chunk_data = chunker.chunk_with_token_counts("synthese", content)
        if chunk_data:
            texts = [c[0] for c in chunk_data]
            embeddings = await embedder.embed_batch(texts)
            for i, ((text, token_count), embedding) in enumerate(zip(chunk_data, embeddings)):
                chunk = KnowledgeChunk(
                    entry_id=entry.id,
                    chunk_index=i,
                    content=text,
                    embedding=embedding,
                    token_count=token_count,
                    metadata_=metadata,
                )
                session.add(chunk)
