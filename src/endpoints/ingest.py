import json
import uuid as uuid_mod

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, select

from src.db.models import AnalyticsRecord, AnalyticsSummary, KnowledgeChunk, KnowledgeEntry, StoredFile
from src.db.session import get_session
from src.embeddings.chunking import ChunkingService
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.schemas.analytics import (
    AnalyticsIngestRequest,
    AnalyticsIngestResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from src.schemas.ingest import IngestDocumentResponse, IngestFileResponse
from src.storage.minio_service import MinIOService, get_minio_service

router = APIRouter()
chunker = ChunkingService()

SUPPORTED_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "application/octet-stream",  # fallback for .txt/.md files
}
SUPPORTED_EXTENSIONS = {".txt", ".md", ".html", ".htm"}


@router.post("/document", response_model=IngestDocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    title: str = Form(None),
    type: str = Form("overig"),
    metadata: str = Form("{}"),
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    # Validate file type
    filename = file.filename or "untitled"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS and file.content_type not in SUPPORTED_TEXT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Supported: .txt, .md, .html",
        )

    # Read content
    raw_bytes = await file.read()
    content = raw_bytes.decode("utf-8", errors="replace")

    # Parse metadata
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}

    # Create entry
    entry = KnowledgeEntry(
        type=type,
        title=title or filename,
        content=content,
        created_by="ingest",
        metadata_=meta,
    )
    session.add(entry)
    await session.flush()

    entry_id = entry.id

    # Chunk
    chunk_data = chunker.chunk_with_token_counts(type, content)
    chunks_created = len(chunk_data)

    # Create chunk rows (embeddings will be filled in background)
    chunk_ids = []
    for i, (text, token_count) in enumerate(chunk_data):
        chunk = KnowledgeChunk(
            entry_id=entry_id,
            chunk_index=i,
            content=text,
            token_count=token_count,
            metadata_=meta,
        )
        session.add(chunk)
        await session.flush()
        chunk_ids.append(chunk.id)

    await session.commit()

    # Generate embeddings in background
    background_tasks.add_task(
        _generate_embeddings, entry_id, chunk_ids, content, [c[0] for c in chunk_data]
    )

    return IngestDocumentResponse(
        entry_id=entry_id,
        chunks_created=chunks_created,
        status="processing",
    )


async def _generate_embeddings(
    entry_id, chunk_ids: list, content: str, chunk_texts: list[str]
):
    """Background task to generate embeddings for entry and chunks."""
    from src.db.engine import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    embedder = EmbeddingService.get_instance()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Embed the full entry
        entry = await session.get(KnowledgeEntry, entry_id)
        if entry:
            entry.embedding = await embedder.embed_text(f"{entry.title}\n\n{content}")

        # Embed chunks
        if chunk_texts:
            embeddings = await embedder.embed_batch(chunk_texts)
            for chunk_id, embedding in zip(chunk_ids, embeddings):
                chunk = await session.get(KnowledgeChunk, chunk_id)
                if chunk:
                    chunk.embedding = embedding

        await session.commit()


@router.post("/file", response_model=IngestFileResponse, status_code=status.HTTP_201_CREATED)
async def ingest_file(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    minio: MinIOService = Depends(get_minio_service),
):
    raw_bytes = await file.read()
    filename = file.filename or "untitled"
    content_type = file.content_type or "application/octet-stream"
    object_key = f"{uuid_mod.uuid4()}/{filename}"

    # Upload to MinIO
    await minio.upload_file(raw_bytes, object_key, content_type)

    # Create DB record
    stored = StoredFile(
        bucket=minio.bucket,
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        file_size=len(raw_bytes),
    )
    session.add(stored)
    await session.commit()
    await session.refresh(stored)

    return IngestFileResponse(
        file_id=stored.id,
        bucket=stored.bucket,
        object_key=stored.object_key,
        filename=stored.filename,
        content_type=stored.content_type,
        file_size=stored.file_size,
    )


@router.post("/analytics", response_model=AnalyticsIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_analytics(
    body: AnalyticsIngestRequest,
    session: AsyncSession = Depends(get_session),
):
    records = []
    for r in body.records:
        record = AnalyticsRecord(
            source=r.source,
            metric_type=r.metric_type,
            dimensions=r.dimensions,
            value=r.value,
            period_start=r.period_start,
            period_end=r.period_end,
            raw_data=r.raw_data,
        )
        records.append(record)

    session.add_all(records)
    await session.commit()

    return AnalyticsIngestResponse(
        created=len(records),
        status="ok",
    )


@router.post("/summarize", response_model=SummarizeResponse, status_code=status.HTTP_201_CREATED)
async def ingest_summarize(
    body: SummarizeRequest,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Generate an AI summary of analytics data for a period.

    Fetches analytics records, aggregates metrics, generates a text summary,
    and stores it as an AnalyticsSummary with embedding for semantic search.
    """
    # Fetch analytics data for the period
    query = (
        select(AnalyticsRecord)
        .where(
            AnalyticsRecord.source == body.source,
            AnalyticsRecord.period_start >= body.period_start,
            AnalyticsRecord.period_end <= body.period_end,
        )
        .order_by(AnalyticsRecord.period_start)
    )
    result = await session.execute(query)
    records = result.scalars().all()

    if not records:
        raise HTTPException(
            status_code=422,
            detail=f"Geen analytische data gevonden voor source='{body.source}' in periode {body.period_start} tot {body.period_end}. Voer eerst data in via /api/v1/ingest/analytics.",
        )

    # Aggregate by metric_type
    aggregations = await _aggregate_metrics(session, body)

    # Generate summary text (template-based; LLM integration planned for future)
    summary_text = _generate_summary_text(body, records, aggregations)

    # Generate insights
    insights = _generate_insights(aggregations)

    # Create AnalyticsSummary with embedding
    embedding = await embedder.embed_text(summary_text)
    summary = AnalyticsSummary(
        period_start=body.period_start,
        period_end=body.period_end,
        source=body.source,
        summary=summary_text,
        insights=insights,
        embedding=embedding,
    )
    session.add(summary)
    await session.commit()
    await session.refresh(summary)

    return SummarizeResponse.model_validate(summary)


async def _aggregate_metrics(
    session: AsyncSession, body: SummarizeRequest
) -> dict[str, dict]:
    """Aggregate metrics by metric_type for the period."""
    base_filter = [
        AnalyticsRecord.source == body.source,
        AnalyticsRecord.period_start >= body.period_start,
        AnalyticsRecord.period_end <= body.period_end,
    ]

    agg_query = (
        select(
            AnalyticsRecord.metric_type,
            func.sum(AnalyticsRecord.value).label("total"),
            func.avg(AnalyticsRecord.value).label("average"),
            func.count(AnalyticsRecord.id).label("count"),
            func.min(AnalyticsRecord.value).label("min_val"),
            func.max(AnalyticsRecord.value).label("max_val"),
        )
        .where(*base_filter)
        .group_by(AnalyticsRecord.metric_type)
    )
    result = await session.execute(agg_query)
    rows = result.all()

    return {
        row.metric_type: {
            "total": float(row.total) if row.total else 0,
            "average": float(row.average) if row.average else 0,
            "count": row.count,
            "min": float(row.min_val) if row.min_val else 0,
            "max": float(row.max_val) if row.max_val else 0,
        }
        for row in rows
    }


def _generate_summary_text(
    body: SummarizeRequest,
    records: list,
    aggregations: dict[str, dict],
) -> str:
    """Generate a human-readable summary of the analytics period."""
    lines = [
        f"Samenvatting {body.source} — {body.period_start} t/m {body.period_end}",
        f"Totaal {len(records)} datapunten geanalyseerd.",
        "",
    ]

    for metric_type, agg in aggregations.items():
        lines.append(f"## {metric_type.capitalize()}")
        lines.append(f"- Totaal: {agg['total']:.2f}")
        lines.append(f"- Gemiddeld: {agg['average']:.2f}")
        lines.append(f"- Aantal records: {agg['count']}")
        lines.append(f"- Minimum: {agg['min']:.2f}")
        lines.append(f"- Maximum: {agg['max']:.2f}")
        lines.append("")

    return "\n".join(lines)


def _generate_insights(aggregations: dict[str, dict]) -> dict:
    """Generate structured insights from aggregations."""
    insights = {
        "metrics_analyzed": list(aggregations.keys()),
        "totals": {mt: agg["total"] for mt, agg in aggregations.items()},
        "averages": {mt: round(agg["average"], 2) for mt, agg in aggregations.items()},
    }

    # Identify best/worst performing metric
    if aggregations:
        best = max(aggregations.items(), key=lambda x: x[1]["total"])
        insights["top_metric"] = {"name": best[0], "total": best[1]["total"]}

    return insights
