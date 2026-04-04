from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.registry.pattern_detector import PatternDetector
from src.registry.tool_registry import ToolRegistry
from src.schemas.registry import (
    EndpointProposal,
    EndpointProposalResponse,
    PatternDetectionResponse,
)

router = APIRouter()
registry = ToolRegistry()
detector = PatternDetector()


# ---------------------------------------------------------------------------
# Proposals (review queue)
# ---------------------------------------------------------------------------


@router.get("/proposals", response_model=list[EndpointProposalResponse])
async def list_proposals(
    session: AsyncSession = Depends(get_session),
):
    """List all endpoint proposals in the review queue (staging)."""
    proposals = await registry.list_proposals(session)
    return proposals


@router.post("/proposals", response_model=EndpointProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    body: EndpointProposal,
    session: AsyncSession = Depends(get_session),
):
    """Manually create a new endpoint proposal."""
    endpoint = await registry.create_proposal(session, body)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


@router.post("/proposals/{proposal_id}/approve", response_model=EndpointProposalResponse)
async def approve_proposal(
    proposal_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Approve a staging proposal → active."""
    try:
        endpoint = await registry.approve(session, proposal_id)
        await session.commit()
        await session.refresh(endpoint)
        return endpoint
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/reject", response_model=EndpointProposalResponse)
async def reject_proposal(
    proposal_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Reject a staging proposal → deprecated."""
    try:
        endpoint = await registry.reject(session, proposal_id)
        await session.commit()
        await session.refresh(endpoint)
        return endpoint
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Active endpoints
# ---------------------------------------------------------------------------


@router.get("/endpoints", response_model=list[EndpointProposalResponse])
async def list_endpoints(
    session: AsyncSession = Depends(get_session),
):
    """List all active dynamic endpoints."""
    endpoints = await registry.list_active(session)
    return endpoints


@router.get("/openapi-extension")
async def get_openapi_extension(
    session: AsyncSession = Depends(get_session),
):
    """Return OpenAPI paths for all active dynamic endpoints."""
    return await registry.get_openapi_extension(session)


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------


@router.post("/detect-patterns", response_model=PatternDetectionResponse)
async def detect_patterns(
    threshold: int = Query(3, ge=1),
    lookback_days: int = Query(30, ge=1),
    auto_create: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Analyze query logs for recurring patterns and optionally create proposals."""
    patterns = await detector.detect_patterns(session, threshold, lookback_days)

    proposals_created = 0
    if auto_create:
        for pattern in patterns:
            proposal = EndpointProposal(
                name=pattern.suggested_name,
                description=f"Auto-detected pattern: {pattern.pattern}",
                endpoint_type="combined",
                query_template=pattern.suggested_template,
                parameters={"sample_queries": pattern.sample_queries[:3]},
                created_by="pattern_detector",
            )
            await registry.create_proposal(session, proposal)
            proposals_created += 1
        await session.commit()

    return PatternDetectionResponse(
        patterns_found=len(patterns),
        proposals_created=proposals_created,
        patterns=patterns,
    )
