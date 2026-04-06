# UPPR Digitaal Brein

## What
Modular knowledge layer for AI agents — bestaande uit een FastAPI MCP-server, PostgreSQL met pgvector voor gecombineerde structured + semantic search, MinIO voor multimodale bestanden, en een Query Planner voor intelligente routering. Het brein compileert kennis automatisch via cross-references en synthese-documenten.

## Tech Stack
- **API**: FastAPI (Python 3.12+), async everywhere
- **Database**: PostgreSQL 16+ with pgvector (via SQLAlchemy async + asyncpg)
- **Migrations**: Alembic
- **Object Store**: MinIO (S3-compatible)
- **Cache**: Redis
- **Embeddings**: sentence-transformers (BAAI/bge-m3, 1024 dim)
- **MCP**: Model Context Protocol server (stdio + remote HTTP)
- **Containers**: Docker Compose

## How to Run
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic revision --autogenerate -m "initial"
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_knowledge
docker compose exec api python -m scripts.seed_analytics
```

API docs: `http://localhost:8000/docs`
MCP server: `http://localhost:8001/mcp`

## Conventions
- Async everywhere (asyncpg + async/await)
- Pydantic v2 for all request/response models
- Soft deletes (is_active=False), never hard delete knowledge entries
- JSONB metadata on most tables for flexible filtering
- All queries logged in query_log table
- OpenAPI spec is the source of truth for endpoints

## Project Structure
- `src/` — Application code (FastAPI app, DB models, endpoints)
- `src/db/models.py` — All SQLAlchemy ORM models (9 tables)
- `src/endpoints/` — API route handlers
- `src/embeddings/` — EmbeddingService (singleton) + ChunkingService
- `src/storage/` — MinIO file storage service
- `src/schemas/` — Pydantic v2 request/response models
- `src/query_planner/` — Query classification + routing + result merging
- `src/synthesis/` — Auto cross-references + synthesis document generation
- `src/services/` — Query logging + brain lint/health check
- `src/middleware/` — API key auth + agent scope validation
- `src/registry/` — Pattern detection + dynamic endpoint registry
- `src/config.py` — pydantic-settings configuration
- `mcp_server.py` — MCP server (24 tools, stdio + remote HTTP)
- `alembic/` — Database migrations
- `scripts/` — Seed scripts and utilities
- `tests/` — Pytest test suite

## Current Phase
All 7 phases complete + Phase 8 (Synthesis) + Lint + MCP. API-first (no embedded UI — agents build their own).
