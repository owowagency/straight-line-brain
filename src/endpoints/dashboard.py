import asyncio
import logging

import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import KnowledgeChunk, KnowledgeEntry
from src.db.session import get_session
from src.schemas.dashboard import (
    EmbeddingPoint,
    EmbeddingVisualizationResponse,
    KnowledgeEntryPreview,
    KnowledgeOverviewResponse,
    KnowledgeTypeStats,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/overview", response_model=KnowledgeOverviewResponse)
async def get_overview(
    session: AsyncSession = Depends(get_session),
):
    """Knowledge overview: entries grouped by type with counts and previews."""
    # Fetch all active entries with chunk counts
    query = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.is_active.is_(True))
        .options(selectinload(KnowledgeEntry.chunks))
        .order_by(KnowledgeEntry.type, KnowledgeEntry.created_at.desc())
    )
    result = await session.execute(query)
    entries = result.scalars().all()

    # Group by type
    type_groups: dict[str, list] = {}
    for entry in entries:
        if entry.type not in type_groups:
            type_groups[entry.type] = []
        type_groups[entry.type].append(entry)

    total_chunks = sum(len(e.chunks) for e in entries)

    types = []
    for entry_type, group in sorted(type_groups.items()):
        types.append(
            KnowledgeTypeStats(
                type=entry_type,
                count=len(group),
                entries=[_entry_preview(e) for e in group],
            )
        )

    # Recent entries (last 5)
    recent = sorted(entries, key=lambda e: e.created_at, reverse=True)[:5]

    return KnowledgeOverviewResponse(
        total_entries=len(entries),
        total_chunks=total_chunks,
        types=types,
        recent_entries=[_entry_preview(e) for e in recent],
    )


@router.get("/embeddings", response_model=EmbeddingVisualizationResponse)
async def get_embeddings(
    kind: str = Query("all", pattern="^(entries|chunks|all)$"),
    session: AsyncSession = Depends(get_session),
):
    """2D embedding coordinates for scatter plot visualization.

    Uses UMAP for dimensionality reduction (1024 → 2D).
    Falls back to PCA if UMAP is unavailable.

    Args:
        kind: "entries" for entry-level only, "chunks" for chunks only, "all" for both
    """
    points: list[EmbeddingPoint] = []
    embeddings: list[list[float]] = []
    metadata: list[dict] = []

    # Fetch entry embeddings
    if kind in ("entries", "all"):
        query = (
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.is_active.is_(True),
                KnowledgeEntry.embedding.is_not(None),
            )
        )
        result = await session.execute(query)
        for entry in result.scalars().all():
            embeddings.append(entry.embedding)
            metadata.append({
                "id": str(entry.id),
                "label": entry.title,
                "type": entry.type,
                "kind": "entry",
                "entry_id": None,
            })

    # Fetch chunk embeddings
    if kind in ("chunks", "all"):
        query = (
            select(KnowledgeChunk, KnowledgeEntry.title, KnowledgeEntry.type)
            .join(KnowledgeEntry, KnowledgeChunk.entry_id == KnowledgeEntry.id)
            .where(
                KnowledgeEntry.is_active.is_(True),
                KnowledgeChunk.embedding.is_not(None),
            )
        )
        result = await session.execute(query)
        for row in result.all():
            chunk = row.KnowledgeChunk
            embeddings.append(chunk.embedding)
            preview = chunk.content[:60] + "..." if len(chunk.content) > 60 else chunk.content
            metadata.append({
                "id": str(chunk.id),
                "label": f"{row.title} (chunk {chunk.chunk_index})",
                "type": row.type,
                "kind": "chunk",
                "entry_id": str(chunk.entry_id),
            })

    if not embeddings:
        return EmbeddingVisualizationResponse(points=[], total=0)

    # Reduce to 2D (run in thread to avoid blocking)
    coords = await asyncio.to_thread(_reduce_to_2d, embeddings)

    for i, (x, y) in enumerate(coords):
        meta = metadata[i]
        points.append(
            EmbeddingPoint(
                id=meta["id"],
                label=meta["label"],
                type=meta["type"],
                kind=meta["kind"],
                x=round(float(x), 4),
                y=round(float(y), 4),
                entry_id=meta["entry_id"],
            )
        )

    return EmbeddingVisualizationResponse(points=points, total=len(points))


def _reduce_to_2d(embeddings: list) -> list[tuple[float, float]]:
    """Reduce high-dimensional embeddings to 2D coordinates."""
    matrix = np.array(embeddings, dtype=np.float32)

    # Need at least 2 points for reduction
    if len(matrix) < 2:
        return [(0.0, 0.0)] * len(matrix)

    try:
        from umap import UMAP

        n_neighbors = min(15, len(matrix) - 1)
        reducer = UMAP(n_components=2, n_neighbors=n_neighbors, random_state=42)
        coords = reducer.fit_transform(matrix)
        return [(float(row[0]), float(row[1])) for row in coords]
    except ImportError:
        logger.warning("umap-learn not installed, falling back to PCA")

    # Fallback: PCA via numpy (no sklearn needed)
    centered = matrix - matrix.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    projected = centered @ vt[:2].T
    return [(float(row[0]), float(row[1])) for row in projected]


def _entry_preview(entry: KnowledgeEntry) -> KnowledgeEntryPreview:
    preview = entry.content[:120] + "..." if len(entry.content) > 120 else entry.content
    return KnowledgeEntryPreview(
        id=entry.id,
        title=entry.title,
        type=entry.type,
        created_at=entry.created_at,
        chunk_count=len(entry.chunks),
        content_preview=preview,
    )
