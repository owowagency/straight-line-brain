from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeType(str, Enum):
    propositie = "propositie"
    icp = "icp"
    dienst = "dienst"
    tone_of_voice = "tone_of_voice"
    werkwijze = "werkwijze"
    bedrijfsprofiel = "bedrijfsprofiel"
    brand = "brand"
    overig = "overig"


class KnowledgeEntryCreate(BaseModel):
    type: KnowledgeType
    title: str
    content: str
    metadata: dict | None = None
    created_by: str = "manual"


class KnowledgeEntryUpdate(BaseModel):
    type: KnowledgeType | None = None
    title: str | None = None
    content: str | None = None
    metadata: dict | None = None


class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_index: int
    content: str
    token_count: int


class KnowledgeEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    title: str
    content: str
    metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    is_active: bool
    chunks: list[KnowledgeChunkResponse] = []


class KnowledgeEntryListResponse(BaseModel):
    items: list[KnowledgeEntryResponse]
    total: int
    page: int
    page_size: int
