from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import KnowledgeChunk, KnowledgeEntry
from src.db.session import get_session
from src.embeddings.chunking import ChunkingService
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.schemas.common import StatusResponse
from src.schemas.knowledge import (
    KnowledgeEntryCreate,
    KnowledgeEntryListResponse,
    KnowledgeEntryResponse,
    KnowledgeEntryUpdate,
)

router = APIRouter()
chunker = ChunkingService()


@router.post("/entries", response_model=KnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: KnowledgeEntryCreate,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    # Create entry
    entry = KnowledgeEntry(
        type=body.type.value,
        title=body.title,
        content=body.content,
        created_by=body.created_by,
    )
    if body.metadata is not None:
        entry.metadata_ = body.metadata

    # Generate entry-level embedding
    entry_embedding = await embedder.embed_text(f"{body.title}\n\n{body.content}")
    entry.embedding = entry_embedding

    session.add(entry)
    await session.flush()  # get entry.id

    # Chunk and embed
    chunk_data = chunker.chunk_with_token_counts(body.type.value, body.content)
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
                metadata_=body.metadata,
            )
            session.add(chunk)

    await session.commit()
    await session.refresh(entry, ["chunks"])
    return _entry_to_response(entry)


@router.get("/entries", response_model=KnowledgeEntryListResponse)
async def list_entries(
    type: str | None = Query(None),
    created_by: str | None = Query(None),
    is_active: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    query = select(KnowledgeEntry).where(KnowledgeEntry.is_active == is_active)

    if type is not None:
        query = query.where(KnowledgeEntry.type == type)
    if created_by is not None:
        query = query.where(KnowledgeEntry.created_by == created_by)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Paginate
    query = (
        query.options(selectinload(KnowledgeEntry.chunks))
        .order_by(KnowledgeEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(query)
    entries = result.scalars().all()

    return KnowledgeEntryListResponse(
        items=[_entry_to_response(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/entries/{entry_id}", response_model=KnowledgeEntryResponse)
async def get_entry(
    entry_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    entry = await _get_entry_or_404(session, entry_id)
    return _entry_to_response(entry)


@router.put("/entries/{entry_id}", response_model=KnowledgeEntryResponse)
async def update_entry(
    entry_id: UUID,
    body: KnowledgeEntryUpdate,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    entry = await _get_entry_or_404(session, entry_id)

    update_data = body.model_dump(exclude_unset=True)
    content_changed = "content" in update_data

    for field, value in update_data.items():
        if field == "metadata":
            entry.metadata_ = value
        elif field == "type":
            setattr(entry, field, value.value if hasattr(value, "value") else value)
        else:
            setattr(entry, field, value)

    # Re-embed and re-chunk if content changed
    if content_changed:
        entry_embedding = await embedder.embed_text(f"{entry.title}\n\n{entry.content}")
        entry.embedding = entry_embedding

        # Delete old chunks
        for chunk in list(entry.chunks):
            await session.delete(chunk)

        # Create new chunks
        entry_type = update_data.get("type", entry.type)
        if hasattr(entry_type, "value"):
            entry_type = entry_type.value
        chunk_data = chunker.chunk_with_token_counts(entry_type, entry.content)
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
                    metadata_=entry.metadata_,
                )
                session.add(chunk)

    await session.commit()
    await session.refresh(entry, ["chunks"])
    return _entry_to_response(entry)


@router.delete("/entries/{entry_id}", response_model=StatusResponse)
async def delete_entry(
    entry_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    entry = await _get_entry_or_404(session, entry_id)
    entry.is_active = False
    await session.commit()
    return StatusResponse(status="ok", message="Entry soft-deleted", id=entry.id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_entry_or_404(session: AsyncSession, entry_id: UUID) -> KnowledgeEntry:
    query = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.id == entry_id, KnowledgeEntry.is_active.is_(True))
        .options(selectinload(KnowledgeEntry.chunks))
    )
    result = await session.execute(query)
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return entry


def _entry_to_response(entry: KnowledgeEntry) -> KnowledgeEntryResponse:
    return KnowledgeEntryResponse(
        id=entry.id,
        type=entry.type,
        title=entry.title,
        content=entry.content,
        metadata=entry.metadata_,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        created_by=entry.created_by,
        is_active=entry.is_active,
        chunks=[
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "token_count": c.token_count,
            }
            for c in sorted(entry.chunks, key=lambda c: c.chunk_index)
        ],
    )
