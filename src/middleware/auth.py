"""
API key authentication and agent scope validation.

Each request can optionally include:
- X-API-Key header → identifies the agent
- The API key maps to an agent_id via the API_KEYS config

Per request, the middleware checks:
1. Is the API key valid?
2. Does the agent have an active scope?
3. Is the requested endpoint in allowed_endpoints (if set)?
4. Is the requested endpoint NOT in blocked_endpoints?

If no API key is provided, the request proceeds without scope restrictions
(for development/testing). In production, set REQUIRE_API_KEY=true.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import AgentScope
from src.db.session import get_session

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _parse_api_keys() -> dict[str, str]:
    """Parse API_KEYS env var into {key: agent_id} mapping.

    Format: "key1:agent_id1,key2:agent_id2"
    """
    settings = get_settings()
    raw = settings.api_keys
    if not raw:
        return {}
    result = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            key, agent_id = pair.split(":", 1)
            result[key.strip()] = agent_id.strip()
    return result


async def get_current_agent(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> AgentScope | None:
    """Validate API key and return agent scope (or None if no key provided)."""
    settings = get_settings()

    if not api_key:
        if settings.require_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-API-Key header required",
            )
        return None

    # Look up agent_id from API key
    key_map = _parse_api_keys()
    agent_id = key_map.get(api_key)
    if agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Look up agent scope
    query = select(AgentScope).where(
        AgentScope.agent_id == agent_id,
        AgentScope.is_active.is_(True),
    )
    result = await session.execute(query)
    scope = result.scalar_one_or_none()

    if scope is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No active scope found for agent '{agent_id}'",
        )

    # Check endpoint permissions
    endpoint_path = request.url.path

    # Check blocked_endpoints
    if scope.blocked_endpoints:
        for blocked in scope.blocked_endpoints:
            if endpoint_path.startswith(blocked) or endpoint_path == blocked:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Agent '{agent_id}' is blocked from endpoint '{endpoint_path}'",
                )

    # Check allowed_endpoints (if set, acts as whitelist)
    if scope.allowed_endpoints:
        allowed = False
        for permit in scope.allowed_endpoints:
            if endpoint_path.startswith(permit) or endpoint_path == permit:
                allowed = True
                break
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent '{agent_id}' is not allowed to access '{endpoint_path}'",
            )

    return scope
