"""
Seed script: push analytische testdata en genereer samenvattingen.

Vul SEGMENTS, METRICS en BASE_VALUES hieronder in met je eigen data.
Het script genereert 12 maanden aan data en kwartaalsamenvattingen.

Draai via:
    docker compose exec api python -m scripts.seed_analytics
"""

import asyncio
import logging
import random
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.models import AnalyticsRecord, AnalyticsSummary
from src.embeddings.service import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vul hier je eigen segmenten en metrics in
# ---------------------------------------------------------------------------
SEGMENTS = [
    # Voorbeeld: "segment_a", "segment_b"
]
METRICS = ["deal", "revenue", "conversie", "pipeline"]
SOURCES = ["crm"]

# Base values per segment per metric (monthly)
# Voorbeeld:
# BASE_VALUES = {
#     "segment_a": {"deal": 10, "revenue": 20000, "conversie": 0.15, "pipeline": 50000},
# }
BASE_VALUES = {}


def _generate_monthly_data() -> list[dict]:
    """Generate 12 months of analytics data for 2025."""
    records = []
    random.seed(42)  # reproducible

    for month in range(1, 13):
        period_start = date(2025, month, 1)
        if month == 12:
            period_end = date(2025, 12, 31)
        else:
            period_end = date(2025, month + 1, 1)

        for segment in SEGMENTS:
            for metric in METRICS:
                base = BASE_VALUES[segment][metric]
                # Add some variance (±30%) and slight uptrend
                trend_factor = 1 + (month - 1) * 0.02  # 2% monthly growth
                noise = random.uniform(0.7, 1.3)
                value = base * trend_factor * noise

                records.append({
                    "source": "salesforce",
                    "metric_type": metric,
                    "dimensions": {"segment": segment},
                    "value": Decimal(str(round(value, 2))),
                    "period_start": period_start,
                    "period_end": period_end,
                    "raw_data": {
                        "segment": segment,
                        "month": month,
                        "base_value": base,
                    },
                })

    return records


async def _generate_quarterly_summaries(
    session: AsyncSession,
    embedder: EmbeddingService,
):
    """Generate summaries for each quarter of 2025."""
    from sqlalchemy import func, select

    quarters = [
        (date(2025, 1, 1), date(2025, 3, 31), "Q1 2025"),
        (date(2025, 4, 1), date(2025, 6, 30), "Q2 2025"),
        (date(2025, 7, 1), date(2025, 9, 30), "Q3 2025"),
        (date(2025, 10, 1), date(2025, 12, 31), "Q4 2025"),
    ]

    for q_start, q_end, q_name in quarters:
        # Aggregate per metric for this quarter
        agg_query = (
            select(
                AnalyticsRecord.metric_type,
                func.sum(AnalyticsRecord.value).label("total"),
                func.avg(AnalyticsRecord.value).label("average"),
                func.count(AnalyticsRecord.id).label("count"),
            )
            .where(
                AnalyticsRecord.source == "salesforce",
                AnalyticsRecord.period_start >= q_start,
                AnalyticsRecord.period_end <= q_end,
            )
            .group_by(AnalyticsRecord.metric_type)
        )
        result = await session.execute(agg_query)
        aggs = {row.metric_type: {"total": float(row.total), "avg": float(row.average), "count": row.count} for row in result.all()}

        if not aggs:
            continue

        # Build summary text
        lines = [
            f"Kwartaalsamenvatting Salesforce — {q_name}",
            f"Periode: {q_start} t/m {q_end}",
            "",
        ]
        for metric, data in sorted(aggs.items()):
            lines.append(f"## {metric.capitalize()}")
            lines.append(f"- Totaal: {data['total']:.2f}")
            lines.append(f"- Gemiddeld per maand: {data['avg']:.2f}")
            lines.append(f"- Aantal datapunten: {data['count']}")
            lines.append("")

        summary_text = "\n".join(lines)
        insights = {
            "quarter": q_name,
            "metrics": aggs,
        }

        # Generate embedding
        embedding = await embedder.embed_text(summary_text)

        summary = AnalyticsSummary(
            period_start=q_start,
            period_end=q_end,
            source="salesforce",
            summary=summary_text,
            insights=insights,
            embedding=embedding,
        )
        session.add(summary)
        logger.info("Created summary: %s", q_name)

    await session.commit()


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    embedder = EmbeddingService.get_instance()

    async with session_factory() as session:
        # Seed analytics records
        data = _generate_monthly_data()
        records = [AnalyticsRecord(**r) for r in data]
        session.add_all(records)
        await session.commit()
        logger.info("Seeded %d analytics records (12 months × 3 segments × 4 metrics)", len(records))

        # Generate quarterly summaries
        await _generate_quarterly_summaries(session, embedder)
        logger.info("Generated 4 quarterly summaries with embeddings")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
