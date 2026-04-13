# Digitaal Brein

Modulaire kennislaag voor AI agents -- FastAPI + PostgreSQL (pgvector) + MCP server.

## Quick Start

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic revision --autogenerate -m "initial"
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_knowledge
docker compose exec api python -m scripts.seed_analytics
```

- API docs: `http://localhost:8000/docs`
- MCP server: `http://localhost:8001/mcp`
- Dashboard: `http://localhost:8000/dashboard`

Root API (`http://localhost:8000/`) now returns a small status JSON with links.

## Local Dev (Terminal Logs)

If you prefer seeing logs directly in your terminal instead of Docker logs:

```bash
pnpm dev
```

This command:
- starts infra containers only (`db`, `redis`, `minio`, `chatbot-db`)
- runs API locally on `:8000`
- runs MCP locally on `:8001`
- runs chatbot locally on `:3000`
- reads keys from root `.env` (set `OPENAI_API_KEY` for GPT models)

Useful helpers:

```bash
pnpm dev:infra   # start only infra containers
pnpm dev:down    # stop docker compose stack
```

## What's Included

- **Knowledge CRUD** -- entries met automatische embedding + chunking
- **Semantic Search** -- vector search via pgvector
- **Structured Analytics** -- sales metrics, pipeline, conversie
- **Query Planner** -- routeert vrije vragen naar juiste databron
- **MCP Server** -- 24 tools voor Claude (stdio + remote HTTP)
- **Synthesis** -- automatische cross-references + synthese-documenten
- **Contacts** -- CRM deduplicatie
- **Brain Lint** -- health check & completeness score

## Customization

### 1. Seed data invullen

Pas de seed scripts aan met je eigen content:

- `scripts/seed_knowledge.py` -- kennisbank entries (bedrijfsprofiel, ICP, diensten, tone of voice)
- `scripts/seed_analytics.py` -- analytische data (segmenten, metrics)

### 2. Theming

Pas het dashboard aan via CSS variabelen in `src/static/dashboard/dashboard.css`:

```css
:root {
  --bg: #05050A;
  --accent: #00DCFF;
  /* etc. */
}
```

### 3. API Keys

Configureer in `.env`:

```
API_KEYS=sk-key1:agent_id_1,sk-key2:agent_id_2
REQUIRE_API_KEY=true
```

## Tech Stack

- FastAPI (Python 3.12+), async everywhere
- PostgreSQL 16+ with pgvector
- Redis (caching)
- MinIO (S3-compatible file storage)
- sentence-transformers (embeddings)
- MCP (Model Context Protocol)
- Docker Compose

## Project Structure

```
src/                  Application code
  db/models.py        SQLAlchemy ORM models
  endpoints/          API route handlers
  embeddings/         EmbeddingService + ChunkingService
  storage/            MinIO file storage
  schemas/            Pydantic v2 models
  query_planner/      Query classification + routing
  synthesis/          Cross-references + synthesis docs
  services/           Query logging + brain lint
  middleware/         API key auth + agent scopes
  registry/           Pattern detection + dynamic endpoints
  config.py           Settings (pydantic-settings)
mcp_server.py         MCP server (24 tools)
alembic/              Database migrations
scripts/              Seed scripts + utilities
tests/                Pytest test suite
```

## Docs

- [MCP Setup Guide](docs/MCP_SETUP.md) -- Claude Code / Desktop / remote configuratie
