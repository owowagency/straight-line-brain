from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentScope
from src.db.session import get_session
from src.schemas.scopes import AgentScopeCreate, AgentScopeResponse, AgentScopeUpdate

router = APIRouter()


@router.post("/", response_model=AgentScopeResponse, status_code=status.HTTP_201_CREATED)
async def create_scope(
    body: AgentScopeCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new agent scope."""
    # Check for duplicate agent_id
    existing = await session.execute(
        select(AgentScope).where(AgentScope.agent_id == body.agent_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scope for agent '{body.agent_id}' already exists",
        )

    scope = AgentScope(
        agent_id=body.agent_id,
        agent_role=body.agent_role,
        allowed_endpoints=body.allowed_endpoints,
        blocked_endpoints=body.blocked_endpoints,
        metadata_filters=body.metadata_filters,
    )
    session.add(scope)
    await session.commit()
    await session.refresh(scope)
    return scope


@router.get("/{agent_id}", response_model=AgentScopeResponse)
async def get_scope(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get scope for a specific agent."""
    scope = await _get_scope_or_404(session, agent_id)
    return scope


@router.put("/{agent_id}", response_model=AgentScopeResponse)
async def update_scope(
    agent_id: str,
    body: AgentScopeUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update scope for a specific agent."""
    scope = await _get_scope_or_404(session, agent_id)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scope, field, value)

    await session.commit()
    await session.refresh(scope)
    return scope


@router.get("/", response_model=list[AgentScopeResponse])
async def list_scopes(
    session: AsyncSession = Depends(get_session),
):
    """List all agent scopes."""
    result = await session.execute(select(AgentScope).order_by(AgentScope.agent_id))
    scopes = result.scalars().all()
    return scopes


async def _get_scope_or_404(session: AsyncSession, agent_id: str) -> AgentScope:
    result = await session.execute(
        select(AgentScope).where(AgentScope.agent_id == agent_id)
    )
    scope = result.scalar_one_or_none()
    if scope is None:
        raise HTTPException(status_code=404, detail=f"No scope found for agent '{agent_id}'")
    return scope
