from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import QueryLog


async def log_query(
    session: AsyncSession,
    endpoint_used: str,
    query_text: str,
    agent_id: str | None = None,
    planner_result: dict | None = None,
    response_time_ms: int | None = None,
) -> None:
    """Log a query to the query_log table. Does NOT commit — caller must commit."""
    entry = QueryLog(
        agent_id=agent_id,
        endpoint_used=endpoint_used,
        query_text=query_text,
        query_planner_result=planner_result,
        response_time_ms=response_time_ms,
    )
    session.add(entry)
