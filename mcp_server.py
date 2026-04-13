"""
MCP Server for the Digitaal Brein.

Exposes all brein endpoints as MCP tools that Claude can call directly.
Communicates with the running Brein API via HTTP.

Two modes:
  1. Local (stdio):   python mcp_server.py
     → For Claude Code / Claude Desktop via local config

  2. Remote (HTTP):   python mcp_server.py --remote
     → Hosted MCP server on port 8001 (Streamable HTTP)
     → Agents connect via: http://localhost:8001/mcp
     → Also available as docker compose service

Usage:
    docker compose up -d          # Start brein API + remote MCP server
    python mcp_server.py          # Local stdio mode
    python mcp_server.py --remote # Remote HTTP mode
"""

import json
import logging
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mcp")

BREIN_URL = os.getenv("BREIN_URL", "http://localhost:8000")
API_KEY = os.getenv("BREIN_API_KEY", "")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

mcp = FastMCP(
    "Digitaal Brein",
    instructions="Knowledge layer voor AI agents — bedrijfskennis, analytics, semantic search. Gebruik deze tools om het Digitaal Brein te bevragen en te vullen.",
    host=MCP_HOST,
    port=MCP_PORT,
)


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def _raise_with_detail(r: httpx.Response) -> None:
    """Raise an error that includes the response body for debugging."""
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise httpx.HTTPStatusError(
            f"{r.status_code} {r.reason_phrase} for {r.url}: {json.dumps(detail, ensure_ascii=False)}",
            request=r.request,
            response=r,
        )


async def _get(path: str, params: dict | None = None) -> dict:
    logger.info("→ GET %s %s", path, params or "")
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.get(path, params=params, headers=_headers())
        _raise_with_detail(r)
        logger.info("← %s %s (%dms)", r.status_code, path, int(r.elapsed.total_seconds() * 1000))
        return r.json()


async def _post(path: str, body: dict | None = None) -> dict:
    logger.info("→ POST %s %s", path, json.dumps(body, ensure_ascii=False)[:200] if body else "")
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.post(path, json=body, headers=_headers())
        _raise_with_detail(r)
        logger.info("← %s %s (%dms)", r.status_code, path, int(r.elapsed.total_seconds() * 1000))
        return r.json()


async def _put(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.put(path, json=body, headers=_headers())
        _raise_with_detail(r)
        return r.json()


async def _delete(path: str) -> dict:
    async with httpx.AsyncClient(base_url=BREIN_URL, timeout=30) as client:
        r = await client.delete(path, headers=_headers())
        _raise_with_detail(r)
        return r.json()


# ===========================================================================
# KNOWLEDGE RETRIEVAL TOOLS
# ===========================================================================


@mcp.tool()
async def get_company_profile() -> str:
    """Haal het bedrijfsprofiel en de propositie op uit het brein."""
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
    """Haal de tone of voice richtlijnen op uit het brein."""
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
        records: JSON array van records, elk met: source, metric_type, dimensions, value, period_start, period_end.
               Voorbeeld: [{"source": "salesforce", "metric_type": "revenue", "value": 50000, "period_start": "2025-01-01", "period_end": "2025-01-31"}]
    """
    parsed = json.loads(records)
    # Accept a single record dict — wrap it in a list
    if isinstance(parsed, dict):
        parsed = [parsed]
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


# ===========================================================================
# STATS TOOLS
# ===========================================================================


@mcp.tool()
async def get_brain_overview() -> str:
    """Haal een overzicht op van alle kennis in het Digitaal Brein.
    Toont entries gegroepeerd per type met counts en content previews."""
    data = await _get("/api/v1/stats/overview")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_embedding_map(kind: str = "all") -> str:
    """Haal 2D embedding coördinaten op voor visualisatie van het brein.
    Retourneert x,y punten die als scatter plot gerenderd kunnen worden.

    Args:
        kind: "entries" voor alleen entries, "chunks" voor chunks, "all" voor beide
    """
    data = await _get("/api/v1/stats/embeddings", params={"kind": kind})
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# SYNTHESIS TOOLS
# ===========================================================================


@mcp.tool()
async def get_related_entries(entry_id: str) -> str:
    """Haal gerelateerde kennisitems op voor een specifiek item.
    Cross-references worden automatisch gedetecteerd bij ingest.

    Args:
        entry_id: UUID van het kennisitem
    """
    data = await _get(f"/api/v1/knowledge/entries/{entry_id}/related")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def query_brain_and_file(query: str, agent_id: str | None = None) -> str:
    """Stel een vraag aan het brein EN sla het antwoord op als 'inzicht' in de kennisbank.
    Gebruik dit als je een waardevol antwoord wilt bewaren voor later.

    Args:
        query: Vrije vraag in natuurlijke taal
        agent_id: Optioneel agent ID
    """
    body = {"query": query, "file_answer": True}
    if agent_id:
        body["agent_id"] = agent_id
    data = await _post("/api/v1/brain/query", body=body)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def lint_brain() -> str:
    """Health check van het Digitaal Brein. Analyseert:
    - Welke kenniscategorieën ontbreken
    - Entries zonder cross-references (orphans)
    - Verouderde entries (90+ dagen niet bijgewerkt)
    - Ontbrekende embeddings
    - Dunne entries met weinig inhoud
    - Ontbrekende contacten of analytics data
    - Ongeresolvede tegenstrijdigheden
    - Entries die wachten op review

    Retourneert een score (0-100), issues, en actiepunten."""
    data = await _post("/api/v1/brain/lint")
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# BRAIN INDEX & NAVIGATION TOOLS
# ===========================================================================


@mcp.tool()
async def get_brain_index() -> str:
    """Inhoudelijke index van het brein: catalogus van alle entries met one-liners,
    gecategoriseerd per type, inclusief cross-reference graph.

    Gebruik dit als eerste stap om het brein te navigeren: scan de index,
    bepaal welke entries relevant zijn, en haal dan specifieke entries op.

    Retourneert: categorieën met entries (id, titel, one-liner, related_count)
    plus een cross-reference graph."""
    data = await _get("/api/v1/brain/index")
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# CHANGELOG TOOLS
# ===========================================================================


@mcp.tool()
async def get_brain_changelog(
    since: str | None = None,
    entry_type: str | None = None,
    limit: int = 50,
) -> str:
    """Chronologisch overzicht van alle kenniswijzigingen in het brein.

    Toont: wanneer entries zijn aangemaakt, bijgewerkt, verwijderd, of
    wanneer synthese-documenten zijn gegenereerd/bijgewerkt.

    Args:
        since: ISO datum filter, bijv. '2026-03-01'
        entry_type: Filter op type, bijv. 'icp', 'dienst'
        limit: Max aantal resultaten (default 50)
    """
    params = {"limit": limit}
    if since:
        params["since"] = since
    if entry_type:
        params["entry_type"] = entry_type
    data = await _get("/api/v1/brain/changelog", params=params)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# WIKI EXPORT TOOLS
# ===========================================================================


@mcp.tool()
async def export_wiki() -> str:
    """Exporteer het volledige brein als een set gelinkte markdown-bestanden.

    Genereert:
    - index.md: inhoudelijke catalogus met links naar alle entries
    - changelog.md: chronologisch overzicht van wijzigingen
    - Per entry: {type}/{slug}.md met content en [[related]] links

    Retourneert een JSON dict met filename → markdown content."""
    data = await _post("/api/v1/brain/wiki-export")
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# CONFLICT DETECTION TOOLS
# ===========================================================================


@mcp.tool()
async def get_potential_conflicts(status: str | None = None) -> str:
    """Toon potentiële tegenstrijdigheden in de kennisbank.

    Detecteert entries met hoge similarity maar verschillende bronnen.
    Dit kunnen entries zijn die elkaar tegenspreken.

    Args:
        status: Filter op status: 'unreviewed', 'confirmed', 'dismissed'
    """
    params = {}
    if status:
        params["status"] = status
    data = await _get("/api/v1/brain/conflicts", params=params)
    return json.dumps(data, indent=2, ensure_ascii=False)


# ===========================================================================
# REVIEW TOOLS
# ===========================================================================


@mcp.tool()
async def list_pending_reviews() -> str:
    """Toon entries die wachten op review voordat ze doorzoekbaar worden.

    Entries met review_required=true bij aanmaak zijn niet doorzoekbaar
    totdat ze goedgekeurd zijn."""
    data = await _get("/api/v1/knowledge/entries", params={
        "is_active": "true",
        "page_size": 100,
    })
    # Filter client-side for pending_review
    items = data.get("items", [])
    pending = [i for i in items if i.get("review_status") == "pending_review"]
    return json.dumps(pending, indent=2, ensure_ascii=False)


@mcp.tool()
async def approve_entry(entry_id: str) -> str:
    """Keur een entry goed die wacht op review.

    Na goedkeuring wordt de entry doorzoekbaar en wordt synthese getriggerd.

    Args:
        entry_id: UUID van de entry om goed te keuren
    """
    data = await _post(f"/api/v1/knowledge/entries/{entry_id}/approve")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def reject_entry(entry_id: str) -> str:
    """Wijs een entry af die wacht op review.

    Args:
        entry_id: UUID van de entry om af te wijzen
    """
    data = await _post(f"/api/v1/knowledge/entries/{entry_id}/reject")
    return json.dumps(data, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if "--remote" in sys.argv or os.getenv("MCP_TRANSPORT") == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
