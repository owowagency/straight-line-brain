"""
Seed script: vul het brein met testdata.

Draai via:
    docker compose exec api python -m scripts.seed_knowledge

Of lokaal:
    python -m scripts.seed_knowledge
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.models import Contact, KnowledgeChunk, KnowledgeEntry
from src.embeddings.chunking import ChunkingService
from src.embeddings.service import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vul hier je eigen content in — voorbeelden hieronder zijn placeholders.
# Types: bedrijfsprofiel, propositie, icp, dienst, tone_of_voice, werkwijze, overig
# ---------------------------------------------------------------------------

KNOWLEDGE_ENTRIES = [
    # Voorbeeld:
    # {
    #     "type": "bedrijfsprofiel",
    #     "title": "Bedrijfsprofiel",
    #     "content": "Beschrijving van je bedrijf...",
    # },
    # {
    #     "type": "icp",
    #     "title": "ICP — Doelgroep A",
    #     "content": "## Profiel\nBeschrijving...\n\n## Pijnpunten\n- ...",
    # },
    # {
    #     "type": "tone_of_voice",
    #     "title": "Tone of Voice",
    #     "content": "Richtlijnen voor communicatie...",
    # },
]

CONTACTS = [
    # Voorbeeld:
    # {"company_name": "Bedrijf A", "contact_name": "Jan Jansen", "email": "jan@bedrijfa.nl", "source": "crm", "status": "client"},
]


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    embedder = EmbeddingService.get_instance()
    chunker = ChunkingService()

    async with session_factory() as session:
        # Seed knowledge entries
        for entry_data in KNOWLEDGE_ENTRIES:
            await _create_entry(session, embedder, chunker, entry_data)

        # Seed contacts
        for contact_data in CONTACTS:
            contact = Contact(**contact_data)
            session.add(contact)

        await session.commit()
        logger.info("Seeded %d knowledge entries and %d contacts", len(KNOWLEDGE_ENTRIES), len(CONTACTS))

    await engine.dispose()


async def _create_entry(
    session: AsyncSession,
    embedder: EmbeddingService,
    chunker: ChunkingService,
    data: dict,
):
    entry = KnowledgeEntry(
        type=data["type"],
        title=data["title"],
        content=data["content"],
        created_by="seed_script",
    )

    # Generate entry embedding
    entry.embedding = await embedder.embed_text(f"{data['title']}\n\n{data['content']}")
    session.add(entry)
    await session.flush()

    # Chunk and embed
    chunk_data = chunker.chunk_with_token_counts(data["type"], data["content"])
    if chunk_data:
        chunk_texts = [c[0] for c in chunk_data]
        chunk_embeddings = await embedder.embed_batch(chunk_texts)

        for i, ((text, token_count), embedding) in enumerate(zip(chunk_data, chunk_embeddings)):
            chunk = KnowledgeChunk(
                entry_id=entry.id,
                chunk_index=i,
                content=text,
                embedding=embedding,
                token_count=token_count,
            )
            session.add(chunk)

    logger.info("Created: [%s] %s (%d chunks)", data["type"], data["title"], len(chunk_data))


if __name__ == "__main__":
    asyncio.run(main())
