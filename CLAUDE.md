# UPPR Digitaal Brein

## What
Modular knowledge layer for AI agents.

## Tech Stack
- **API**: FastAPI (Python 3.12+), async everywhere
- **Database**: PostgreSQL 16+ with pgvector (via SQLAlchemy async + asyncpg)
- **Migrations**: Alembic
- **Object Store**: MinIO (S3-compatible)
- **Cache**: Redis
- **Embeddings**: sentence-transformers (BAAI/bge-m3, 1024 dim)
- **Containers**: Docker Compose

## How to Run
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
```

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
- `src/config.py` — pydantic-settings configuration
- `alembic/` — Database migrations
- `scripts/` — Seed scripts and utilities
- `tests/` — Pytest test suite

## Current Phase
Phase 4: Query Planner — Intelligente Routering
