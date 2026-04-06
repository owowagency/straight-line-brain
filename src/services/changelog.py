"""
Knowledge changelog: records all mutations to knowledge entries.

Append-only log of creates, updates, deletes, and synthesis events.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChangeLog

logger = logging.getLogger(__name__)


async def log_change(
    session: AsyncSession,
    *,
    entry_id: UUID | None,
    action: str,
    entry_title: str,
    entry_type: str,
    change_summary: str,
    triggered_by: str = "manual",
    metadata: dict | None = None,
) -> None:
    """Append a changelog entry. Does NOT commit — caller is responsible."""
    record = KnowledgeChangeLog(
        entry_id=entry_id,
        action=action,
        entry_title=entry_title,
        entry_type=entry_type,
        change_summary=change_summary,
        triggered_by=triggered_by,
        metadata_=metadata,
    )
    session.add(record)
    logger.debug("Changelog: %s '%s' (%s)", action, entry_title, triggered_by)
