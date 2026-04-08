import time
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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
from src.schemas.retrieval import RelatedEntryInfo
from src.services.changelog import log_change
from src.services.query_logger import log_query
from src.synthesis.generator import SynthesisGenerator
from src.synthesis.relations import RelationDetector

router = APIRouter()
chunker = ChunkingService()
relation_detector = RelationDetector()
synthesis_generator = SynthesisGenerator()


# ---------------------------------------------------------------------------
# Narrow "fast lane" endpoints — direct DB lookups
# ---------------------------------------------------------------------------


@router.get("/icp", response_model=list[KnowledgeEntryResponse])
async def get_icp(
    segment: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Return ICP profiles, optionally filtered by segment name."""
    t0 = time.perf_counter()
    query = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.type == "icp", KnowledgeEntry.is_active.is_(True))
        .options(selectinload(KnowledgeEntry.chunks))
    )
    if segment:
        query = query.where(KnowledgeEntry.title.ilike(f"%{segment}%"))
    result = await session.execute(query)
    entries = result.scalars().all()

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(session, "knowledge/icp", f"segment={segment}", response_time_ms=ms)
    await session.commit()
    return [_entry_to_response(e) for e in entries]


@router.get("/company", response_model=list[KnowledgeEntryResponse])
async def get_company(
    session: AsyncSession = Depends(get_session),
):
    """Return company profile (bedrijfsprofiel + propositie)."""
    t0 = time.perf_counter()
    query = (
        select(KnowledgeEntry)
        .where(
            KnowledgeEntry.type.in_(["bedrijfsprofiel", "propositie"]),
            KnowledgeEntry.is_active.is_(True),
        )
        .options(selectinload(KnowledgeEntry.chunks))
    )
    result = await session.execute(query)
    entries = result.scalars().all()

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(session, "knowledge/company", "company profile", response_time_ms=ms)
    await session.commit()
    return [_entry_to_response(e) for e in entries]


@router.get("/tone-of-voice", response_model=KnowledgeEntryResponse | None)
async def get_tone_of_voice(
    session: AsyncSession = Depends(get_session),
):
    """Return tone of voice guidelines."""
    t0 = time.perf_counter()
    query = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.type == "tone_of_voice", KnowledgeEntry.is_active.is_(True))
        .options(selectinload(KnowledgeEntry.chunks))
        .limit(1)
    )
    result = await session.execute(query)
    entry = result.scalar_one_or_none()

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(session, "knowledge/tone-of-voice", "tone of voice", response_time_ms=ms)
    await session.commit()

    if entry is None:
        raise HTTPException(status_code=404, detail="No tone of voice entry found")
    return _entry_to_response(entry)


@router.get("/services", response_model=list[KnowledgeEntryResponse])
async def get_services(
    segment: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Return services, optionally filtered by segment keyword."""
    t0 = time.perf_counter()
    query = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.type == "dienst", KnowledgeEntry.is_active.is_(True))
        .options(selectinload(KnowledgeEntry.chunks))
    )
    if segment:
        query = query.where(KnowledgeEntry.content.ilike(f"%{segment}%"))
    result = await session.execute(query)
    entries = result.scalars().all()

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(session, "knowledge/services", f"segment={segment}", response_time_ms=ms)
    await session.commit()
    return [_entry_to_response(e) for e in entries]


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/entries", response_model=KnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: KnowledgeEntryCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    # Create entry
    entry = KnowledgeEntry(
        type=body.type.value,
        title=body.title,
        content=body.content,
        created_by=body.created_by,
        review_status="pending_review" if body.review_required else "approved",
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

    # Log to changelog
    await log_change(
        session,
        entry_id=entry.id,
        action="created",
        entry_title=body.title,
        entry_type=body.type.value,
        change_summary=f"Nieuwe entry aangemaakt ({len(body.content.split())} woorden)",
        triggered_by=body.created_by,
    )

    await session.commit()
    entry = await _get_entry_or_404(session, entry.id)

    # Trigger synthesis in background only for approved entries
    if entry.review_status == "approved":
        background_tasks.add_task(
            _post_ingest_synthesis, entry.id, body.type.value
        )

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

    # Log to changelog
    changed_fields = list(update_data.keys())
    await log_change(
        session,
        entry_id=entry.id,
        action="updated",
        entry_title=entry.title,
        entry_type=entry.type,
        change_summary=f"Velden bijgewerkt: {', '.join(changed_fields)}",
        triggered_by="manual",
        metadata={"changed_fields": changed_fields},
    )

    await session.commit()
    entry = await _get_entry_or_404(session, entry_id)
    return _entry_to_response(entry)


@router.delete("/entries/{entry_id}", response_model=StatusResponse)
async def delete_entry(
    entry_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    entry = await _get_entry_or_404(session, entry_id)
    entry.is_active = False

    await log_change(
        session,
        entry_id=entry.id,
        action="deleted",
        entry_title=entry.title,
        entry_type=entry.type,
        change_summary="Entry soft-deleted",
        triggered_by="manual",
    )

    await session.commit()
    return StatusResponse(status="ok", message="Entry soft-deleted", id=entry.id)


# ---------------------------------------------------------------------------
# Review / Approve
# ---------------------------------------------------------------------------


@router.post("/entries/{entry_id}/approve", response_model=StatusResponse)
async def approve_entry(
    entry_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Approve a pending_review entry. Makes it searchable and triggers synthesis."""
    entry = await _get_entry_or_404(session, entry_id)
    if entry.review_status == "approved":
        return StatusResponse(status="ok", message="Entry is al goedgekeurd", id=entry.id)

    entry.review_status = "approved"

    await log_change(
        session,
        entry_id=entry.id,
        action="approved",
        entry_title=entry.title,
        entry_type=entry.type,
        change_summary="Entry goedgekeurd na review",
        triggered_by="manual",
    )

    await session.commit()

    # Now trigger synthesis that was skipped during creation
    background_tasks.add_task(
        _post_ingest_synthesis, entry.id, entry.type
    )

    return StatusResponse(status="ok", message="Entry goedgekeurd", id=entry.id)


@router.post("/entries/{entry_id}/reject", response_model=StatusResponse)
async def reject_entry(
    entry_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Reject a pending_review entry."""
    entry = await _get_entry_or_404(session, entry_id)
    entry.review_status = "rejected"

    await log_change(
        session,
        entry_id=entry.id,
        action="rejected",
        entry_title=entry.title,
        entry_type=entry.type,
        change_summary="Entry afgewezen na review",
        triggered_by="manual",
    )

    await session.commit()
    return StatusResponse(status="ok", message="Entry afgewezen", id=entry.id)


# ---------------------------------------------------------------------------
# Related entries
# ---------------------------------------------------------------------------


@router.get("/entries/{entry_id}/related", response_model=list[RelatedEntryInfo])
async def get_related_entries(
    entry_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get entries related to this entry (via auto-detected cross-references)."""
    entry = await _get_entry_or_404(session, entry_id)
    related = (entry.metadata_ or {}).get("related_entries", [])
    return [RelatedEntryInfo(**r) for r in related]


# ---------------------------------------------------------------------------
# Background synthesis
# ---------------------------------------------------------------------------


async def _post_ingest_synthesis(entry_id: UUID, entry_type: str) -> None:
    """Background task: detect relations, conflicts, and generate synthesis documents."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from src.db.engine import engine

    embedder = EmbeddingService.get_instance()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Detect and store relations
        relations = await relation_detector.detect_related(session, entry_id)
        if relations:
            await relation_detector.update_entry_relations(session, entry_id, relations)

        # 2. Detect potential contradictions
        await relation_detector.detect_conflicts(session, entry_id)

        # 3. Generate synthesis documents if triggered
        synthesis_types = synthesis_generator.should_generate(entry_type)
        for syn_type in synthesis_types:
            await synthesis_generator.generate(syn_type, session, embedder)

        await session.commit()


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
        review_status=entry.review_status,
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
