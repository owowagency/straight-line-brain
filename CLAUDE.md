# UPPR Digitaal Brein

## What
Modular knowledge layer for AI agents.

## Tech Stack
- **API**: FastAPI (Python 3.12+), async everywhere
- **Database**: PostgreSQL 16+ with pgvector (via SQLAlchemy async + asyncpg)
- **Migrations**: Alembic
- **Object Store**: MinIO (S3-compatible)
- **Cache**: Redis
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

## Current Phase
Phase 1: Foundation
