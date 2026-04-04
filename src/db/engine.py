from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config import get_settings


def build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=(settings.log_level == "debug"),
        pool_size=20,
        max_overflow=10,
    )


engine = build_engine()
