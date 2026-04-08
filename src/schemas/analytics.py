from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsRecordCreate(BaseModel):
    source: str
    metric_type: str
    dimensions: dict | None = None
    value: float
    period_start: date
    period_end: date
    raw_data: dict | None = None


class AnalyticsIngestRequest(BaseModel):
    records: list[AnalyticsRecordCreate]


class AnalyticsIngestResponse(BaseModel):
    created: int
    status: str


class SummarizeRequest(BaseModel):
    source: str
    period_start: date
    period_end: date


class SummarizeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    period_start: date
    period_end: date
    summary: str
    insights: dict | None = None
    created_at: datetime
