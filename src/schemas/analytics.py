from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class AnalyticsRecordCreate(BaseModel):
    source: str
    metric_type: str
    dimensions: dict | None = None
    value: Decimal
    period_start: date
    period_end: date
    raw_data: dict | None = None


class AnalyticsIngestRequest(BaseModel):
    records: list[AnalyticsRecordCreate]


class AnalyticsIngestResponse(BaseModel):
    created: int
    status: str
