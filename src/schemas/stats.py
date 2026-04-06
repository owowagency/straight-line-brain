from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class KnowledgeEntryPreview(BaseModel):
    id: UUID
    title: str
    type: str
    created_at: datetime
    chunk_count: int
    content_preview: str


class KnowledgeTypeStats(BaseModel):
    type: str
    count: int
    entries: list[KnowledgeEntryPreview]


class KnowledgeOverviewResponse(BaseModel):
    total_entries: int
    total_chunks: int
    types: list[KnowledgeTypeStats]
    recent_entries: list[KnowledgeEntryPreview]


class EmbeddingPoint(BaseModel):
    id: str
    label: str
    type: str
    kind: str  # "entry" or "chunk"
    x: float
    y: float
    entry_id: str | None = None


class EmbeddingVisualizationResponse(BaseModel):
    points: list[EmbeddingPoint]
    total: int
