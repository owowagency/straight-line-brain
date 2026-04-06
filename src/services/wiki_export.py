"""
WikiExportService: renders the knowledge base as a set of interlinked markdown files.

Generates:
- index.md — categorized catalog of all entries with one-liners
- {type}/{slug}.md — per entry with content, metadata, and [[related]] links
- changelog.md — chronological evolution log
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChangeLog, KnowledgeEntry

logger = logging.getLogger(__name__)

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


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")[:80]


class WikiExportService:
    async def export(self, session: AsyncSession) -> dict[str, str]:
        """Generate full wiki export as a dict of filename -> markdown content."""
        # Fetch all active entries
        result = await session.execute(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.is_active.is_(True))
            .order_by(KnowledgeEntry.type, KnowledgeEntry.title)
        )
        entries = list(result.scalars().all())

        # Build slug lookup for linking
        slug_lookup: dict[str, str] = {}  # entry_id -> path
        for entry in entries:
            slug = _slugify(entry.title)
            slug_lookup[str(entry.id)] = f"{entry.type}/{slug}"

        files: dict[str, str] = {}

        # Generate per-entry files
        by_type: dict[str, list] = {}
        for entry in entries:
            by_type.setdefault(entry.type, []).append(entry)
            path = slug_lookup[str(entry.id)]
            files[f"{path}.md"] = self._render_entry(entry, slug_lookup)

        # Generate index.md
        files["index.md"] = self._render_index(by_type, slug_lookup)

        # Generate changelog.md
        changelog_result = await session.execute(
            select(KnowledgeChangeLog)
            .order_by(KnowledgeChangeLog.created_at.desc())
            .limit(100)
        )
        changelog_entries = list(changelog_result.scalars().all())
        files["changelog.md"] = self._render_changelog(changelog_entries)

        return files

    def _render_entry(
        self,
        entry: KnowledgeEntry,
        slug_lookup: dict[str, str],
    ) -> str:
        created = entry.created_at.strftime("%Y-%m-%d")
        updated = entry.updated_at.strftime("%Y-%m-%d")
        label = TYPE_LABELS.get(entry.type, entry.type)

        lines = [
            f"# {entry.title}",
            "",
            f"**Type:** {label} | **Aangemaakt:** {created} | **Bijgewerkt:** {updated}",
            "",
            entry.content,
            "",
        ]

        # Related entries
        related = (entry.metadata_ or {}).get("related_entries", [])
        if related:
            lines.append("## Gerelateerde kennis")
            for rel in related:
                rel_path = slug_lookup.get(rel["id"], rel["id"])
                score = rel.get("score", 0)
                lines.append(f"- [[{rel_path}|{rel['title']}]] (score: {score:.2f})")
            lines.append("")

        # Source info
        lines.append("## Bronvermeldingen")
        lines.append(f"- Aangemaakt door: {entry.created_by}")
        lines.append(f"- Laatste wijziging: {updated}")

        source_entries = (entry.metadata_ or {}).get("source_entries", [])
        if source_entries:
            lines.append(f"- Bronnen: {len(source_entries)} entries")

        return "\n".join(lines)

    def _render_index(
        self,
        by_type: dict[str, list],
        slug_lookup: dict[str, str],
    ) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        total = sum(len(v) for v in by_type.values())

        lines = [
            "# Digitaal Brein — Index",
            "",
            f"*Automatisch gegenereerd op {now}. {total} entries in {len(by_type)} categorieën.*",
            "",
        ]

        for entry_type in sorted(by_type.keys()):
            entries = by_type[entry_type]
            label = TYPE_LABELS.get(entry_type, entry_type)
            lines.append(f"## {label} ({len(entries)})")
            lines.append("")
            for entry in entries:
                path = slug_lookup[str(entry.id)]
                one_liner = entry.content[:100].replace("\n", " ").strip()
                if len(entry.content) > 100:
                    one_liner = one_liner.rsplit(" ", 1)[0] + "..."
                lines.append(f"- [[{path}|{entry.title}]] — {one_liner}")
            lines.append("")

        return "\n".join(lines)

    def _render_changelog(self, changelog: list[KnowledgeChangeLog]) -> str:
        lines = [
            "# Digitaal Brein — Changelog",
            "",
            "*Chronologisch overzicht van alle kenniswijzigingen.*",
            "",
        ]

        if not changelog:
            lines.append("*Nog geen wijzigingen geregistreerd.*")
            return "\n".join(lines)

        for entry in changelog:
            ts = entry.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"- **{ts}** | `{entry.action}` | "
                f"**{entry.entry_title}** ({entry.entry_type}) — "
                f"{entry.change_summary} _{entry.triggered_by}_"
            )

        return "\n".join(lines)
