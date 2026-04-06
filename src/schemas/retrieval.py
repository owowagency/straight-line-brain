from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------------------------
class SemanticSearchRequest(BaseModel):
    query: str
    metadata_filter: dict | None = None
    top_k: int = 5
    entry_type: str | None = None


class SemanticChunkResult(BaseModel):
    chunk_id: UUID
    entry_id: UUID
    entry_title: str
    entry_type: str
    content: str
    score: float
    metadata: dict | None = None


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SemanticChunkResult]
    total: int


# ---------------------------------------------------------------------------
# Contact Check
# ---------------------------------------------------------------------------
class ContactCheckRequest(BaseModel):
    company_name: str
    email: str | None = None


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    contact_name: str | None = None
    email: str | None = None
    source: str
    status: str
    created_at: datetime


class ContactCheckResponse(BaseModel):
    exists: bool
    contact: ContactResponse | None = None


# ---------------------------------------------------------------------------
# Structured Query
# ---------------------------------------------------------------------------
class StructuredQueryResponse(BaseModel):
    metric_type: str
    period_start: date | None = None
    period_end: date | None = None
    records: list[dict]
    total: int
    aggregation: dict | None = None


# ---------------------------------------------------------------------------
# Brain Query
# ---------------------------------------------------------------------------
class BrainQueryRequest(BaseModel):
    query: str
    agent_id: str | None = None
    file_answer: bool = False


class BrainQueryResponse(BaseModel):
    query: str
    strategy: str
    results: list[SemanticChunkResult]
    planner_metadata: dict | None = None
    filed_as: str | None = None  # entry ID if answer was filed


class RelatedEntryInfo(BaseModel):
    id: str
    title: str
    type: str
    score: float


# ---------------------------------------------------------------------------
# Brain Index
# ---------------------------------------------------------------------------
class BrainIndexEntry(BaseModel):
    id: str
    title: str
    one_liner: str
    related_count: int = 0
    updated_at: datetime
    created_by: str


class BrainIndexCategory(BaseModel):
    type: str
    label: str
    count: int
    entries: list[BrainIndexEntry]


class CrossReferenceEdge(BaseModel):
    source: str  # entry id
    target: str  # related entry id
    score: float


class BrainIndexResponse(BaseModel):
    generated_at: datetime
    total_entries: int
    categories: list[BrainIndexCategory]
    cross_reference_graph: list[CrossReferenceEdge]


# ---------------------------------------------------------------------------
# Knowledge Changelog
# ---------------------------------------------------------------------------
class ChangeLogEntry(BaseModel):
    id: str
    entry_id: str | None = None
    action: str
    entry_title: str
    entry_type: str
    change_summary: str
    triggered_by: str
    metadata: dict | None = None
    created_at: datetime


class ChangeLogResponse(BaseModel):
    items: list[ChangeLogEntry]
    total: int


# ---------------------------------------------------------------------------
# Wiki Export
# ---------------------------------------------------------------------------
class WikiExportResponse(BaseModel):
    generated_at: datetime
    total_files: int
    files: dict[str, str]  # filename -> markdown content


# ---------------------------------------------------------------------------
# Potential Conflicts
# ---------------------------------------------------------------------------
class ConflictInfo(BaseModel):
    entry_id: str
    entry_title: str
    conflicting_entry_id: str
    conflicting_entry_title: str
    similarity_score: float
    reason: str
    status: str = "unreviewed"  # unreviewed, confirmed, dismissed
