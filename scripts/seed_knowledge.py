"""
Seed script: vul het brein met echte content uit data/ folder.

Leest .txt bestanden uit data/ — elk bestand bevat:
  - Regel 1: type: <knowledge_type>
  - Regel 2: title: <titel>
  - Regel 3+: content (markdown)

Idempotent: wist eerst alle bestaande entries en herseeds alles.

Draai via:
    docker compose exec api python -m scripts.seed_knowledge

Of lokaal:
    python -m scripts.seed_knowledge
"""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.models import Contact, KnowledgeChunk, KnowledgeEntry
from src.embeddings.chunking import ChunkingService
from src.embeddings.service import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_entries_from_files() -> list[dict]:
    """Read all .txt files from data/ and parse them into entry dicts."""
    entries = []
    if not DATA_DIR.exists():
        logger.warning("Data directory not found: %s", DATA_DIR)
        return entries

    for filepath in sorted(DATA_DIR.glob("*.txt")):
        text = filepath.read_text(encoding="utf-8")
        lines = text.split("\n")

        # Parse header lines
        entry_type = None
        title = None
        content_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith("type:") and entry_type is None:
                entry_type = stripped.split(":", 1)[1].strip()
                content_start = i + 1
            elif stripped.lower().startswith("title:") and title is None:
                title = stripped.split(":", 1)[1].strip()
                content_start = i + 1
            elif entry_type and title:
                break

        if not entry_type or not title:
            logger.warning("Skipping %s — missing type or title header", filepath.name)
            continue

        # Content is everything after the header, with leading blank lines stripped
        content = "\n".join(lines[content_start:]).strip()

        if not content:
            logger.warning("Skipping %s — no content", filepath.name)
            continue

        entries.append({
            "type": entry_type,
            "title": title,
            "content": content,
            "source_file": filepath.name,
        })
        logger.info("Loaded: [%s] %s (%s)", entry_type, title, filepath.name)

    return entries


async def clear_existing(session: AsyncSession):
    """Remove all existing knowledge entries and contacts for a clean reseed."""
    await session.execute(delete(KnowledgeChunk))
    await session.execute(delete(KnowledgeEntry))
    await session.execute(delete(Contact))
    await session.commit()
    logger.info("Cleared existing knowledge entries, chunks, and contacts")


async def create_entry(
    session: AsyncSession,
    embedder: EmbeddingService,
    chunker: ChunkingService,
    data: dict,
):
    """Create a knowledge entry with embedding and chunks."""
    entry = KnowledgeEntry(
        type=data["type"],
        title=data["title"],
        content=data["content"],
        created_by="seed_script",
    )

    # Generate entry-level embedding
    entry.embedding = await embedder.embed_text(f"{data['title']}\n\n{data['content']}")
    session.add(entry)
    await session.flush()

    # Chunk and embed
    chunk_data = chunker.chunk_with_token_counts(data["type"], data["content"])
    if chunk_data:
        chunk_texts = [c[0] for c in chunk_data]
        chunk_embeddings = await embedder.embed_batch(chunk_texts)

        for i, ((text, token_count), embedding) in enumerate(
            zip(chunk_data, chunk_embeddings)
        ):
            chunk = KnowledgeChunk(
                entry_id=entry.id,
                chunk_index=i,
                content=text,
                embedding=embedding,
                token_count=token_count,
            )
            session.add(chunk)

    logger.info(
        "Created: [%s] %s (%d chunks)",
        data["type"],
        data["title"],
        len(chunk_data) if chunk_data else 0,
    )


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    embedder = EmbeddingService.get_instance()
    chunker = ChunkingService()

    # Load entries from data files
    entries = load_entries_from_files()
    if not entries:
        logger.error("No entries found in %s — nothing to seed", DATA_DIR)
        await engine.dispose()
        return

    async with session_factory() as session:
        # Clear existing data for clean reseed
        await clear_existing(session)

        # Seed knowledge entries
        for entry_data in entries:
            await create_entry(session, embedder, chunker, entry_data)

        await session.commit()

        # Summary
        type_counts: dict[str, int] = {}
        for e in entries:
            type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1

        logger.info("Seeded %d knowledge entries:", len(entries))
        for t, count in sorted(type_counts.items()):
            logger.info("  %s: %d", t, count)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
