from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://brein:brein_dev@db:5432/uppr_brein"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket: str = "uppr-brein"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "debug"

    # Embeddings
    embedding_model: str = "microsoft/harrier-oss-v1-0.6b"
    embedding_dimension: int = 1024

    # API Security
    api_keys: str = ""  # Format: "key1:agent_id1,key2:agent_id2"
    require_api_key: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
