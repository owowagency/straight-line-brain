import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.db.engine import engine
from src.endpoints import brain, contacts, ingest, knowledge, registry_api, scopes, semantic, stats, structured
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
    title="Digitaal Brein",
    description="Knowledge Layer voor AI Agents",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "service": "digitaal-brein",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
    }

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    logger.error(
        "Validation error on %s %s: %s | Body: %s",
        request.method, request.url.path, exc.errors(), body.decode(errors="replace")[:2000],
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(structured.router, prefix="/api/v1/structured", tags=["structured"])
app.include_router(semantic.router, prefix="/api/v1/semantic", tags=["semantic"])
app.include_router(brain.router, prefix="/api/v1/brain", tags=["brain"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["contacts"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(registry_api.router, prefix="/api/v1/registry", tags=["registry"])
app.include_router(scopes.router, prefix="/api/v1/scopes", tags=["scopes"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(static_dir / "dashboard"), html=True), name="dashboard")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "digitaal-brein"}
