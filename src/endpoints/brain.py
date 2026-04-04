import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.query_planner.planner import QueryPlanner
from src.schemas.retrieval import BrainQueryRequest, BrainQueryResponse
from src.services.query_logger import log_query

router = APIRouter()
planner = QueryPlanner()


@router.post("/query", response_model=BrainQueryResponse)
async def query_brain(
    body: BrainQueryRequest,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Free-form brain query routed through the Query Planner."""
    t0 = time.perf_counter()

    # 1. Plan: classify the query
    plan = await planner.plan(body.query)

    # 2. Execute: run the appropriate queries
    execution = await planner.execute(plan, body.query, session, embedder)

    ms = int((time.perf_counter() - t0) * 1000)

    planner_meta = {
        "intent": plan.intent,
        "confidence": plan.confidence,
        "reason": plan.reason,
        "merge_strategy": plan.merge_strategy,
        "narrow_type": plan.narrow_type,
        "narrow_params": plan.narrow_params,
        "strategy_used": execution["strategy"],
        "response_time_ms": ms,
        "merged_data": execution.get("merged"),
    }

    await log_query(
        session,
        "brain/query",
        body.query,
        agent_id=body.agent_id,
        planner_result=planner_meta,
        response_time_ms=ms,
    )
    await session.commit()

    return BrainQueryResponse(
        query=body.query,
        strategy=execution["strategy"],
        results=execution["results"],
        planner_metadata=planner_meta,
    )
