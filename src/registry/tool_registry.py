"""
ToolRegistry: manages dynamic endpoint lifecycle.

Lifecycle:
1. STAGING — proposal created, awaiting review
2. ACTIVE — approved, available via API
3. DEPRECATED — no longer used, can be removed
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RegisteredEndpoint
from src.schemas.registry import EndpointProposal

logger = logging.getLogger(__name__)


class ToolRegistry:
    async def create_proposal(
        self, session: AsyncSession, proposal: EndpointProposal
    ) -> RegisteredEndpoint:
        """Register a new endpoint in staging."""
        endpoint = RegisteredEndpoint(
            name=proposal.name,
            description=proposal.description,
            endpoint_type=proposal.endpoint_type,
            query_template=proposal.query_template,
            parameters=proposal.parameters,
            created_by=proposal.created_by,
            status="staging",
        )
        session.add(endpoint)
        await session.flush()
        logger.info("Created endpoint proposal: %s (staging)", proposal.name)
        return endpoint

    async def approve(
        self, session: AsyncSession, endpoint_id: UUID
    ) -> RegisteredEndpoint:
        """Promote from staging to active."""
        endpoint = await self._get_or_404(session, endpoint_id)
        if endpoint.status != "staging":
            raise ValueError(f"Cannot approve endpoint with status '{endpoint.status}'")
        endpoint.status = "active"
        logger.info("Approved endpoint: %s → active", endpoint.name)
        return endpoint

    async def reject(
        self, session: AsyncSession, endpoint_id: UUID
    ) -> RegisteredEndpoint:
        """Reject a staging proposal (sets to deprecated)."""
        endpoint = await self._get_or_404(session, endpoint_id)
        if endpoint.status != "staging":
            raise ValueError(f"Cannot reject endpoint with status '{endpoint.status}'")
        endpoint.status = "deprecated"
        logger.info("Rejected endpoint: %s → deprecated", endpoint.name)
        return endpoint

    async def deprecate(
        self, session: AsyncSession, endpoint_id: UUID
    ) -> RegisteredEndpoint:
        """Deprecate an active endpoint."""
        endpoint = await self._get_or_404(session, endpoint_id)
        endpoint.status = "deprecated"
        logger.info("Deprecated endpoint: %s", endpoint.name)
        return endpoint

    async def record_usage(
        self, session: AsyncSession, endpoint_id: UUID
    ) -> None:
        """Increment usage count and update last_used_at."""
        await session.execute(
            update(RegisteredEndpoint)
            .where(RegisteredEndpoint.id == endpoint_id)
            .values(
                usage_count=RegisteredEndpoint.usage_count + 1,
                last_used_at=datetime.now(timezone.utc),
            )
        )

    async def list_active(
        self, session: AsyncSession
    ) -> list[RegisteredEndpoint]:
        """List all active endpoints."""
        result = await session.execute(
            select(RegisteredEndpoint)
            .where(RegisteredEndpoint.status == "active")
            .order_by(RegisteredEndpoint.name)
        )
        return list(result.scalars().all())

    async def list_proposals(
        self, session: AsyncSession
    ) -> list[RegisteredEndpoint]:
        """List all staging proposals."""
        result = await session.execute(
            select(RegisteredEndpoint)
            .where(RegisteredEndpoint.status == "staging")
            .order_by(RegisteredEndpoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_openapi_extension(
        self, session: AsyncSession
    ) -> dict:
        """Return OpenAPI paths for all active dynamic endpoints."""
        active = await self.list_active(session)
        paths = {}
        for ep in active:
            path_key = f"/api/v1/dynamic/{ep.name}"
            paths[path_key] = {
                "get": {
                    "summary": ep.description,
                    "operationId": ep.name,
                    "parameters": ep.parameters or [],
                    "tags": ["dynamic"],
                }
            }
        return paths

    async def _get_or_404(
        self, session: AsyncSession, endpoint_id: UUID
    ) -> RegisteredEndpoint:
        endpoint = await session.get(RegisteredEndpoint, endpoint_id)
        if endpoint is None:
            raise ValueError(f"Endpoint {endpoint_id} not found")
        return endpoint
