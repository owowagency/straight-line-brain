import time
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AnalyticsRecord
from src.db.session import get_session
from src.schemas.retrieval import StructuredQueryResponse
from src.services.query_logger import log_query

router = APIRouter()

AGGREGATE_FUNCS = {
    "sum": func.sum,
    "avg": func.avg,
    "count": func.count,
    "min": func.min,
    "max": func.max,
}


@router.get("/query", response_model=StructuredQueryResponse)
async def query_structured(
    metric_type: str = Query(...),
    source: str | None = Query(None),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    aggregate: str = Query("sum"),
    session: AsyncSession = Depends(get_session),
):
    """Query analytics data with optional filters and aggregation."""
    t0 = time.perf_counter()

    # Build base filter
    base_filter = [AnalyticsRecord.metric_type == metric_type]
    if source:
        base_filter.append(AnalyticsRecord.source == source)
    if period_start:
        base_filter.append(AnalyticsRecord.period_start >= period_start)
    if period_end:
        base_filter.append(AnalyticsRecord.period_end <= period_end)

    # Fetch records
    query = select(AnalyticsRecord).where(*base_filter).order_by(AnalyticsRecord.period_start)
    result = await session.execute(query)
    records = result.scalars().all()

    # Compute aggregation
    agg_func = AGGREGATE_FUNCS.get(aggregate, func.sum)
    agg_query = select(
        agg_func(AnalyticsRecord.value).label("value"),
        func.count(AnalyticsRecord.id).label("count"),
    ).where(*base_filter)
    agg_result = await session.execute(agg_query)
    agg_row = agg_result.one()

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(
        session,
        "structured/query",
        f"metric_type={metric_type} source={source} period={period_start}-{period_end}",
        response_time_ms=ms,
    )
    await session.commit()

    return StructuredQueryResponse(
        metric_type=metric_type,
        period_start=period_start,
        period_end=period_end,
        records=[
            {
                "id": str(r.id),
                "source": r.source,
                "metric_type": r.metric_type,
                "dimensions": r.dimensions,
                "value": float(r.value),
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
            }
            for r in records
        ],
        total=len(records),
        aggregation={
            "function": aggregate,
            "value": float(agg_row.value) if agg_row.value is not None else None,
            "count": agg_row.count,
        },
    )
