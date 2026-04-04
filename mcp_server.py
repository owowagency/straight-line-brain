"""
MCP Server for the UPPR Digitaal Brein.

Exposes all brein endpoints as MCP tools that Claude can call directly.
Communicates with the running Brein API via HTTP.

Two modes:
  1. Local (stdio):   python mcp_server.py
     → For Claude Code / Claude Desktop via local config

  2. Remote (HTTP):   python mcp_server.py --remote
     → Hosted MCP server on port 8001 (Streamable HTTP)
     → UPPR.OS agents connect via: http://brein.uppr.dev:8001/mcp
     → Also available as docker compose service

Usage:
    docker compose up -d          # Start brein API + remote MCP server
    python mcp_server.py          # Local stdio mode
    python mcp_server.py --remote # Remote HTTP mode
"""

import json
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

BREIN_URL = os.getenv("BREIN_URL", "http://localhost:8000")
API_KEY = os.getenv("BREIN_API_KEY", "")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

mcp = FastMCP(
    "UPPR Digitaal Brein",
    instructions="Knowledge layer voor AI agents — bedrijfskennis, analytics, semantic search. Gebruik deze tools om het Digitaal Brein te bevragen en te vullen.",
    host=MCP_HOST,
    port=MCP_PORT,
)


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.get(path, params=params, headers=_headers())
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.post(path, json=body, headers=_headers())
        r.raise_for_status()
        return r.json()


async def _put(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.put(path, json=body, headers=_headers())
        r.raise_for_status()
        return r.json()


async def _delete(path: str) -> dict:
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.delete(path, headers=_headers())
        r.raise_for_status()
        return r.json()


# ===========================================================================
# KNOWLEDGE RETRIEVAL TOOLS
# ===========================================================================


@mcp.tool()
async def get_company_profile() -> str:
    """Haal het bedrijfsprofiel en de propositie op van UPPR."""
    data = await _get("/api/v1/knowledge/company")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_icp_profile(segment: str | None = None) -> str:
    """Haal het Ideal Customer Profile (ICP) op, optioneel gefilterd op segment.

    Args:
        segment: Segmentnaam om op te filteren (bijv. "vve", "woningcorporatie", "schilder")
    """
    params = {"segment": segment} if segment else None
    data = await _get("/api/v1/knowledge/icp", params=params)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_tone_of_voice() -> str:
    """Haal de tone of voice richtlijnen op van UPPR."""
    data = await _get("/api/v1/knowledge/tone-of-voice")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_services(segment: str | None = None) -> str:
    """Haal de diensten op, optioneel gefilterd op segment.

    Args:
        segment: Segmentnaam om diensten op te filteren
    """
    params = {"segment": segment} if segment else None
    data = await _get("/api/v1/knowledge/services", params=params)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# KNOWLEDGE CRUD TOOLS
# ===========================================================================


@mcp.tool()
async def list_knowledge_entries(
    type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> str:
    """Lijst alle kennisbank-entries op met optionele filters.

    Args:
        type: Filter op type (propositie, icp, dienst, tone_of_voice, werkwijze, bedrijfsprofiel, overig)
        page: Paginanummer (start bij 1)
        page_size: Aantal resultaten per pagina
    """
    params = {"page": page, "page_size": page_size}
    if type:
        params["type"] = type
    data = await _get("/api/v1/knowledge/entries", params=params)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_knowledge_entry(entry_id: str) -> str:
    """Haal een specifieke kennisbank-entry op met alle chunks.

    Args:
        entry_id: UUID van de entry
    """
    data = await _get(f"/api/v1/knowledge/entries/{entry_id}")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def create_knowledge_entry(
    type: str,
    title: str,
    content: str,
    metadata: str | None = None,
) -> str:
    """Maak een nieuwe kennisbank-entry aan met automatische embedding en chunking.

    Args:
        type: Type entry (propositie, icp, dienst, tone_of_voice, werkwijze, bedrijfsprofiel, overig)
        title: Titel van de entry
        content: Volledige tekst/inhoud
        metadata: Optionele JSON metadata als string
    """
    body = {"type": type, "title": title, "content": content}
    if metadata:
        body["metadata"] = json.loads(metadata)
    data = await _post("/api/v1/knowledge/entries", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def update_knowledge_entry(
    entry_id: str,
    title: str | None = None,
    content: str | None = None,
    type: str | None = None,
) -> str:
    """Update een bestaande kennisbank-entry. Herberekent embeddings als content wijzigt.

    Args:
        entry_id: UUID van de entry
        title: Nieuwe titel (optioneel)
        content: Nieuwe inhoud (optioneel, triggert re-embedding)
        type: Nieuw type (optioneel)
    """
    body = {}
    if title:
        body["title"] = title
    if content:
        body["content"] = content
    if type:
        body["type"] = type
    data = await _put(f"/api/v1/knowledge/entries/{entry_id}", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def delete_knowledge_entry(entry_id: str) -> str:
    """Soft-delete een kennisbank-entry (is_active=False).

    Args:
        entry_id: UUID van de entry
    """
    data = await _delete(f"/api/v1/knowledge/entries/{entry_id}")
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# SEARCH TOOLS
# ===========================================================================


@mcp.tool()
async def search_knowledge(
    query: str,
    top_k: int = 5,
    entry_type: str | None = None,
) -> str:
    """Zoek door de kennisbank met semantische vector search.

    Args:
        query: Zoekvraag in natuurlijke taal
        top_k: Aantal resultaten (standaard 5)
        entry_type: Filter op type entry (optioneel)
    """
    body = {"query": query, "top_k": top_k}
    if entry_type:
        body["entry_type"] = entry_type
    data = await _post("/api/v1/semantic/search", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def query_brain(query: str, agent_id: str | None = None) -> str:
    """Stel een vrije vraag aan het Digitaal Brein. Het brein routeert automatisch
    naar de juiste databron (kennis, analytics, of beide).

    Args:
        query: Vrije vraag in natuurlijke taal (bijv. "Hoe presteren we bij VVE-beheerders?")
        agent_id: Optioneel agent ID voor logging
    """
    body = {"query": query}
    if agent_id:
        body["agent_id"] = agent_id
    data = await _post("/api/v1/brain/query", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# CONTACTS TOOLS
# ===========================================================================


@mcp.tool()
async def check_contact(
    company_name: str,
    email: str | None = None,
) -> str:
    """Check of een contact/bedrijf al bestaat in het CRM (deduplicatie).

    Args:
        company_name: Bedrijfsnaam om te checken
        email: Optioneel e-mailadres voor extra matching
    """
    body = {"company_name": company_name}
    if email:
        body["email"] = email
    data = await _post("/api/v1/contacts/check", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# STRUCTURED / ANALYTICS TOOLS
# ===========================================================================


@mcp.tool()
async def query_analytics(
    metric_type: str,
    source: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    aggregate: str = "sum",
) -> str:
    """Query analytische data (sales metrics, conversie, pipeline).

    Args:
        metric_type: Type metric (deal, revenue, conversie, pipeline)
        source: Databron (bijv. "salesforce")
        period_start: Startdatum (YYYY-MM-DD)
        period_end: Einddatum (YYYY-MM-DD)
        aggregate: Aggregatiefunctie (sum, avg, count, min, max)
    """
    params = {"metric_type": metric_type, "aggregate": aggregate}
    if source:
        params["source"] = source
    if period_start:
        params["period_start"] = period_start
    if period_end:
        params["period_end"] = period_end
    data = await _get("/api/v1/structured/query", params=params)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# INGEST TOOLS
# ===========================================================================


@mcp.tool()
async def ingest_analytics(records: str) -> str:
    """Push analytische data naar het brein (bulk).

    Args:
        records: JSON array van records, elk met: source, metric_type, dimensions, value, period_start, period_end
    """
    parsed = json.loads(records)
    body = {"records": parsed}
    data = await _post("/api/v1/ingest/analytics", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def summarize_analytics(
    source: str,
    period_start: str,
    period_end: str,
) -> str:
    """Genereer een samenvatting van analytische data voor een periode.
    De samenvatting wordt opgeslagen met embedding en is doorzoekbaar.

    Args:
        source: Databron (bijv. "salesforce")
        period_start: Startdatum (YYYY-MM-DD)
        period_end: Einddatum (YYYY-MM-DD)
    """
    body = {
        "source": source,
        "period_start": period_start,
        "period_end": period_end,
    }
    data = await _post("/api/v1/ingest/summarize", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# ADMIN TOOLS
# ===========================================================================


@mcp.tool()
async def list_agent_scopes() -> str:
    """Lijst alle agent scopes/permissies op."""
    data = await _get("/api/v1/scopes/")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_registry_proposals() -> str:
    """Lijst alle endpoint-voorstellen in de review queue."""
    data = await _get("/api/v1/registry/proposals")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_active_endpoints() -> str:
    """Lijst alle actieve dynamische endpoints."""
    data = await _get("/api/v1/registry/endpoints")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def detect_query_patterns(
    threshold: int = 3,
    auto_create: bool = False,
) -> str:
    """Analyseer query logs op terugkerende patronen en maak optioneel voorstellen aan.

    Args:
        threshold: Minimaal aantal herhalingen om een patroon te detecteren
        auto_create: Maak automatisch endpoint-voorstellen aan voor gevonden patronen
    """
    params = {"threshold": threshold, "auto_create": auto_create}
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.post(
            "/api/v1/registry/detect-patterns",
            params=params,
            headers=_headers(),
        )
        r.raise_for_status()
        data = r.json()
    return json.dumps(data, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if "--remote" in sys.argv or os.getenv("MCP_TRANSPORT") == "streamable-http":
        # Remote mode: hosted MCP server via Streamable HTTP
        # UPPR.OS agents connect to http://<host>:<port>/mcp
        mcp.run(transport="streamable-http")
    else:
        # Local mode: stdio transport for Claude Code / Claude Desktop
        mcp.run()
