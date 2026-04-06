import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChangeLog, KnowledgeEntry
from src.db.session import get_session
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.query_planner.planner import QueryPlanner
from src.schemas.lint import LintReport
from src.schemas.retrieval import (
    BrainIndexCategory,
    BrainIndexEntry,
    BrainIndexResponse,
    BrainQueryRequest,
    BrainQueryResponse,
    ChangeLogEntry,
    ChangeLogResponse,
    ConflictInfo,
    CrossReferenceEdge,
    WikiExportResponse,
)
from src.services.lint import LintService
from src.services.query_logger import log_query
from src.services.wiki_export import WikiExportService

router = APIRouter()
planner = QueryPlanner()
linter = LintService()
wiki_exporter = WikiExportService()

TYPE_LABELS = {
    "bedrijfsprofiel": "Bedrijfsprofiel",
    "propositie": "Propositie",
    "icp": "Klantprofielen (ICP)",
    "dienst": "Diensten",
    "tone_of_voice": "Schrijfstijl",
    "werkwijze": "Werkwijze",
    "brand": "Merk",
    "synthese": "Synthese",
    "inzicht": "Inzichten",
    "overig": "Overig",
}


@router.post("/query", response_model=BrainQueryResponse)
async def query_brain(
    body: BrainQueryRequest,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Free-form brain query routed through the Query Planner."""
    t0 = time.perf_counter()

    # 1. Plan: classify the query
    plan = await planner.plan(body.query)

    # 2. Execute: run the appropriate queries
    execution = await planner.execute(plan, body.query, session, embedder)

    ms = int((time.perf_counter() - t0) * 1000)

    planner_meta = {
        "intent": plan.intent,
        "confidence": plan.confidence,
        "reason": plan.reason,
        "merge_strategy": plan.merge_strategy,
        "narrow_type": plan.narrow_type,
        "narrow_params": plan.narrow_params,
        "strategy_used": execution["strategy"],
        "response_time_ms": ms,
        "merged_data": execution.get("merged"),
    }

    await log_query(
        session,
        "brain/query",
        body.query,
        agent_id=body.agent_id,
        planner_result=planner_meta,
        response_time_ms=ms,
    )

    # 3. File answer as knowledge entry if requested
    filed_id = None
    if body.file_answer and execution["results"]:
        filed_id = await _file_answer(
            session, embedder, body.query, execution, planner_meta
        )

    await session.commit()

    return BrainQueryResponse(
        query=body.query,
        strategy=execution["strategy"],
        results=execution["results"],
        planner_metadata=planner_meta,
        filed_as=filed_id,
    )


async def _file_answer(
    session: AsyncSession,
    embedder: EmbeddingService,
    query: str,
    execution: dict,
    planner_meta: dict,
) -> str | None:
    """File a brain query answer as a new 'inzicht' knowledge entry."""
    results = execution["results"]
    if not results:
        return None

    # Build answer content from results
    lines = [f"# Inzicht: {query}", ""]
    for r in results[:5]:
        lines.append(f"**{r.entry_title}** ({r.entry_type})")
        lines.append(r.content)
        lines.append("")

    content = "\n".join(lines)
    embedding = await embedder.embed_text(f"{query}\n\n{content}")

    entry = KnowledgeEntry(
        type="inzicht",
        title=f"Inzicht: {query[:100]}",
        content=content,
        created_by=planner_meta.get("agent_id", "brain_query"),
        metadata_={
            "source_query": query,
            "strategy_used": execution["strategy"],
            "filed_at": datetime.now(timezone.utc).isoformat(),
            "auto_generated": True,
        },
        embedding=embedding,
    )
    session.add(entry)
    await session.flush()
    return str(entry.id)


@router.post("/lint", response_model=LintReport)
async def lint_brain(
    session: AsyncSession = Depends(get_session),
):
    """Health check: analyze the brein for gaps, orphans, stale content, and suggestions."""
    return await linter.run_lint(session)


# ---------------------------------------------------------------------------
# Content Index for Agents
# ---------------------------------------------------------------------------


@router.get("/index", response_model=BrainIndexResponse)
async def get_brain_index(
    session: AsyncSession = Depends(get_session),
):
    """Inhoudelijke index van het brein: catalogus met one-liners per entry,
    gecategoriseerd per type, met cross-reference graph.

    Ontworpen als navigatie-instrument voor agents: lees eerst de index,
    bepaal welke entries relevant zijn, en drill dan dieper."""
    result = await session.execute(
        select(KnowledgeEntry)
        .where(
            KnowledgeEntry.is_active.is_(True),
            KnowledgeEntry.review_status == "approved",
        )
        .order_by(KnowledgeEntry.type, KnowledgeEntry.title)
    )
    entries = list(result.scalars().all())

    # Group by type
    by_type: dict[str, list[KnowledgeEntry]] = {}
    for entry in entries:
        by_type.setdefault(entry.type, []).append(entry)

    categories = []
    for entry_type in sorted(by_type.keys()):
        group = by_type[entry_type]
        label = TYPE_LABELS.get(entry_type, entry_type.replace("_", " ").title())
        cat_entries = []
        for e in group:
            one_liner = e.content[:100].replace("\n", " ").strip()
            if len(e.content) > 100:
                one_liner = one_liner.rsplit(" ", 1)[0] + "..."
            related = (e.metadata_ or {}).get("related_entries", [])
            cat_entries.append(BrainIndexEntry(
                id=str(e.id),
                title=e.title,
                one_liner=one_liner,
                related_count=len(related),
                updated_at=e.updated_at,
                created_by=e.created_by,
            ))
        categories.append(BrainIndexCategory(
            type=entry_type,
            label=label,
            count=len(group),
            entries=cat_entries,
        ))

    # Build cross-reference graph
    graph: list[CrossReferenceEdge] = []
    seen_edges: set[tuple[str, str]] = set()
    for entry in entries:
        related = (entry.metadata_ or {}).get("related_entries", [])
        for rel in related:
            edge_key = tuple(sorted((str(entry.id), rel["id"])))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                graph.append(CrossReferenceEdge(
                    source=str(entry.id),
                    target=rel["id"],
                    score=rel.get("score", 0),
                ))

    return BrainIndexResponse(
        generated_at=datetime.now(timezone.utc),
        total_entries=len(entries),
        categories=categories,
        cross_reference_graph=graph,
    )


# ---------------------------------------------------------------------------
# Knowledge Changelog
# ---------------------------------------------------------------------------


@router.get("/changelog", response_model=ChangeLogResponse)
async def get_changelog(
    since: str | None = Query(None, description="ISO date filter, e.g. 2026-03-01"),
    entry_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Chronologisch overzicht van alle kenniswijzigingen (append-only evolutie-log)."""
    query = (
        select(KnowledgeChangeLog)
        .order_by(KnowledgeChangeLog.created_at.desc())
        .limit(limit)
    )
    if since:
        query = query.where(
            KnowledgeChangeLog.created_at >= datetime.fromisoformat(since)
        )
    if entry_type:
        query = query.where(KnowledgeChangeLog.entry_type == entry_type)

    result = await session.execute(query)
    items = result.scalars().all()

    return ChangeLogResponse(
        items=[
            ChangeLogEntry(
                id=str(item.id),
                entry_id=str(item.entry_id) if item.entry_id else None,
                action=item.action,
                entry_title=item.entry_title,
                entry_type=item.entry_type,
                change_summary=item.change_summary,
                triggered_by=item.triggered_by,
                metadata=item.metadata_,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=len(items),
    )


# ---------------------------------------------------------------------------
# Wiki Export
# ---------------------------------------------------------------------------


@router.post("/wiki-export", response_model=WikiExportResponse)
async def wiki_export(
    session: AsyncSession = Depends(get_session),
):
    """Exporteer het brein als een set gelinkte markdown-bestanden.

    Retourneert een JSON dict met filename → markdown content.
    Bevat: index.md, changelog.md, en per entry een {type}/{slug}.md bestand."""
    files = await wiki_exporter.export(session)
    return WikiExportResponse(
        generated_at=datetime.now(timezone.utc),
        total_files=len(files),
        files=files,
    )


# ---------------------------------------------------------------------------
# Potential Conflicts
# ---------------------------------------------------------------------------


@router.get("/conflicts", response_model=list[ConflictInfo])
async def get_conflicts(
    status: str | None = Query(None, description="Filter: unreviewed, confirmed, dismissed"),
    session: AsyncSession = Depends(get_session),
):
    """Lijst van potentiële tegenstrijdigheden in de kennisbank.

    Detecteert entries met hoge similarity maar verschillende bronnen."""
    result = await session.execute(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.is_active.is_(True))
    )
    entries = result.scalars().all()

    conflicts: list[ConflictInfo] = []
    for entry in entries:
        entry_conflicts = (entry.metadata_ or {}).get("potential_conflicts", [])
        for c in entry_conflicts:
            if status and c.get("status") != status:
                continue
            conflicts.append(ConflictInfo(**c))

    return conflicts
