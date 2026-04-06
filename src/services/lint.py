"""
Knowledge health check: analyzes the brein for gaps, orphans, and issues.

Checks:
1. Coverage — which knowledge categories are filled?
2. Orphans — entries without cross-references
3. Stale — entries not updated in a long time
4. Gaps — expected categories with missing or thin content
5. Embeddings — entries/chunks missing embeddings
6. Quality — very short entries, entries without chunks
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChunk, KnowledgeEntry, Contact, AnalyticsRecord
from src.schemas.lint import LintIssue, LintReport

logger = logging.getLogger(__name__)

# Expected knowledge types for a healthy brein
EXPECTED_TYPES = {
    "bedrijfsprofiel": {"min": 1, "label": "Bedrijfsprofiel"},
    "propositie": {"min": 1, "label": "Propositie"},
    "icp": {"min": 1, "label": "Klantprofielen (ICP)"},
    "dienst": {"min": 1, "label": "Diensten"},
    "tone_of_voice": {"min": 1, "label": "Schrijfstijl"},
    "werkwijze": {"min": 1, "label": "Werkwijze"},
}

STALE_DAYS = 90  # entries older than this without update are "stale"


class LintService:
    async def run_lint(self, session: AsyncSession) -> LintReport:
        """Run all health checks and return a comprehensive report."""
        issues: list[LintIssue] = []

        # Fetch all active entries
        result = await session.execute(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.is_active.is_(True))
        )
        entries = list(result.scalars().all())

        # Group by type
        by_type: dict[str, list] = {}
        for e in entries:
            by_type.setdefault(e.type, []).append(e)

        # 1. Coverage check
        coverage = {}
        for etype, config in EXPECTED_TYPES.items():
            count = len(by_type.get(etype, []))
            coverage[etype] = {
                "label": config["label"],
                "count": count,
                "minimum": config["min"],
                "ok": count >= config["min"],
            }
            if count == 0:
                issues.append(LintIssue(
                    severity="warning",
                    category="missing",
                    message=f"Geen {config['label']} gevonden. Dit is essentiële bedrijfskennis.",
                    action=f"Voeg minimaal {config['min']} {config['label'].lower()} toe.",
                ))
            elif count < config["min"]:
                issues.append(LintIssue(
                    severity="info",
                    category="gap",
                    message=f"Slechts {count} {config['label'].lower()} (minimum: {config['min']}).",
                    action=f"Overweeg meer {config['label'].lower()} toe te voegen.",
                ))

        # 2. Orphan check — entries without cross-references
        for e in entries:
            related = (e.metadata_ or {}).get("related_entries", [])
            if not related and e.type not in ("synthese", "inzicht"):
                issues.append(LintIssue(
                    severity="info",
                    category="orphan",
                    message=f"'{e.title}' heeft geen cross-references naar andere entries.",
                    entry_id=str(e.id),
                    action="Voer de synthese opnieuw uit of voeg gerelateerde kennis toe.",
                ))

        # 3. Stale check — entries not updated recently
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
        for e in entries:
            if e.type in ("synthese", "inzicht"):
                continue
            if e.updated_at and e.updated_at.replace(tzinfo=timezone.utc) < cutoff:
                issues.append(LintIssue(
                    severity="info",
                    category="stale",
                    message=f"'{e.title}' is al {STALE_DAYS}+ dagen niet bijgewerkt.",
                    entry_id=str(e.id),
                    action="Controleer of de inhoud nog actueel is.",
                ))

        # 4. Missing embeddings
        no_embed = [e for e in entries if e.embedding is None]
        if no_embed:
            issues.append(LintIssue(
                severity="warning",
                category="gap",
                message=f"{len(no_embed)} entries hebben geen embedding (niet doorzoekbaar).",
                action="Werk deze entries bij om embeddings te genereren.",
            ))

        # 5. Quality — very short content
        for e in entries:
            if e.type in ("synthese", "inzicht"):
                continue
            word_count = len(e.content.split())
            if word_count < 20:
                issues.append(LintIssue(
                    severity="info",
                    category="gap",
                    message=f"'{e.title}' is erg kort ({word_count} woorden).",
                    entry_id=str(e.id),
                    action="Overweeg meer inhoud toe te voegen.",
                ))

        # 6. Contacts check
        contact_count = (await session.execute(
            select(func.count(Contact.id))
        )).scalar_one()
        if contact_count == 0:
            issues.append(LintIssue(
                severity="suggestion",
                category="missing",
                message="Geen contacten in het brein. Contact-deduplicatie werkt niet zonder data.",
                action="Importeer contacten vanuit je CRM.",
            ))

        # 7. Analytics check
        analytics_count = (await session.execute(
            select(func.count(AnalyticsRecord.id))
        )).scalar_one()
        if analytics_count == 0:
            issues.append(LintIssue(
                severity="suggestion",
                category="missing",
                message="Geen analytische data. Structured queries zullen geen resultaten geven.",
                action="Push sales data via /ingest/analytics.",
            ))

        # 8. Conflict check — unresolved potential contradictions
        conflict_count = 0
        for e in entries:
            conflicts = (e.metadata_ or {}).get("potential_conflicts", [])
            unreviewed = [c for c in conflicts if c.get("status") == "unreviewed"]
            if unreviewed:
                conflict_count += len(unreviewed)
                issues.append(LintIssue(
                    severity="warning",
                    category="conflict",
                    message=f"'{e.title}' heeft {len(unreviewed)} ongeresolvede "
                            f"potentiële tegenstrijdigheid(en).",
                    entry_id=str(e.id),
                    action="Review de conflicten en markeer als bevestigd of afgewezen.",
                ))

        # 9. Pending review check
        pending_review = [e for e in entries if e.review_status == "pending_review"]
        if pending_review:
            issues.append(LintIssue(
                severity="info",
                category="review",
                message=f"{len(pending_review)} entries wachten op review.",
                action="Keur de entries goed of wijs ze af via /entries/{id}/approve.",
            ))

        # 10. Synthesis check — are they up to date?
        synthese_entries = by_type.get("synthese", [])
        if not synthese_entries and len(entries) > 5:
            issues.append(LintIssue(
                severity="suggestion",
                category="gap",
                message="Geen synthese-documenten. Het brein compileert kennis nog niet.",
                action="Voeg een entry toe of werk een ICP/dienst bij om synthese te triggeren.",
            ))

        # Calculate health score
        total_entries = len(entries)
        coverage_ok = sum(1 for c in coverage.values() if c["ok"])
        coverage_total = len(EXPECTED_TYPES)

        warnings = sum(1 for i in issues if i.severity == "warning")
        infos = sum(1 for i in issues if i.severity == "info")

        score = 100
        score -= warnings * 15
        score -= infos * 3
        if total_entries == 0:
            score = 0
        else:
            score = max(0, min(100, score))

        stats = {
            "total_entries": total_entries,
            "total_types": len(by_type),
            "contacts": contact_count,
            "analytics_records": analytics_count,
            "synthese_entries": len(synthese_entries),
            "inzicht_entries": len(by_type.get("inzicht", [])),
            "entries_with_embeddings": total_entries - len(no_embed),
            "entries_without_relations": sum(
                1 for e in entries
                if not (e.metadata_ or {}).get("related_entries")
                and e.type not in ("synthese", "inzicht")
            ),
            "unresolved_conflicts": conflict_count,
            "pending_review": len(pending_review),
        }

        return LintReport(
            score=score,
            total_issues=len(issues),
            issues=issues,
            coverage=coverage,
            stats=stats,
        )
