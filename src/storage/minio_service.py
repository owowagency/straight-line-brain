from __future__ import annotations

import io
import logging
from typing import ClassVar

from miniopy_async import Minio

from src.config import get_settings

logger = logging.getLogger(__name__)


class MinIOService:
    _instance: ClassVar[MinIOService | None] = None

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=False,
        )
        self.bucket = settings.minio_bucket

    @classmethod
    def get_instance(cls) -> MinIOService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def ensure_bucket(self) -> None:
        exists = await self.client.bucket_exists(self.bucket)
        if not exists:
            await self.client.make_bucket(self.bucket)
            logger.info("Created MinIO bucket: %s", self.bucket)

    async def upload_file(
        self,
        file_data: bytes,
        object_key: str,
        content_type: str,
    ) -> str:
        data = io.BytesIO(file_data)
        size = len(file_data)
        await self.client.put_object(
            self.bucket,
            object_key,
            data,
            size,
            content_type=content_type,
        )
        logger.info("Uploaded %s to %s/%s (%d bytes)", object_key, self.bucket, object_key, size)
        return object_key


def get_minio_service() -> MinIOService:
    return MinIOService.get_instance()
