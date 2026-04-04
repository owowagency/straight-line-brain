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


class BrainQueryResponse(BaseModel):
    query: str
    strategy: str
    results: list[SemanticChunkResult]
    planner_metadata: dict | None = None
