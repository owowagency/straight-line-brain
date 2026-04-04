from uuid import UUID

from pydantic import BaseModel


class IngestDocumentResponse(BaseModel):
    entry_id: UUID
    chunks_created: int
    status: str


class IngestFileResponse(BaseModel):
    file_id: UUID
    bucket: str
    object_key: str
    filename: str
    content_type: str
    file_size: int
