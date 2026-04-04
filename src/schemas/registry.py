from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EndpointProposal(BaseModel):
    name: str
    description: str
    endpoint_type: str  # structured, semantic, combined
    query_template: str
    parameters: dict | None = None
    created_by: str = "pattern_detector"


class EndpointProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    endpoint_type: str
    query_template: str
    parameters: dict | None = None
    openapi_schema: dict | None = None
    usage_count: int
    status: str
    created_by: str
    created_at: datetime
    last_used_at: datetime | None = None


class PatternDetectionResult(BaseModel):
    pattern: str
    frequency: int
    sample_queries: list[str]
    suggested_name: str
    suggested_template: str


class PatternDetectionResponse(BaseModel):
    patterns_found: int
    proposals_created: int
    patterns: list[PatternDetectionResult]
