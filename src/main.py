import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.engine import engine
from src.endpoints import brain, contacts, ingest, knowledge, registry_api, semantic, structured
from src.storage.minio_service import MinIOService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure MinIO bucket exists
    try:
        minio = MinIOService.get_instance()
        await minio.ensure_bucket()
    except Exception:
        logger.warning("Could not connect to MinIO — bucket creation skipped")
    yield
    await engine.dispose()


app = FastAPI(
    title="UPPR Digitaal Brein",
    description="Knowledge Layer voor AI Agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(structured.router, prefix="/api/v1/structured", tags=["structured"])
app.include_router(semantic.router, prefix="/api/v1/semantic", tags=["semantic"])
app.include_router(brain.router, prefix="/api/v1/brain", tags=["brain"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["contacts"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(registry_api.router, prefix="/api/v1/registry", tags=["registry"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "uppr-digitaal-brein"}
