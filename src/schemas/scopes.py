from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentScopeCreate(BaseModel):
    agent_id: str
    agent_role: str
    allowed_endpoints: list[str] | None = None
    blocked_endpoints: list[str] | None = None
    metadata_filters: dict | None = None


class AgentScopeUpdate(BaseModel):
    agent_role: str | None = None
    allowed_endpoints: list[str] | None = None
    blocked_endpoints: list[str] | None = None
    metadata_filters: dict | None = None
    is_active: bool | None = None


class AgentScopeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: str
    agent_role: str
    allowed_endpoints: list | None = None
    blocked_endpoints: list | None = None
    metadata_filters: dict | None = None
    is_active: bool
    created_at: datetime
