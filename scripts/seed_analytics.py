"""
Seed script: analytische data.

Momenteel geen analytics data beschikbaar voor Straight-Line Leadership.
Dit script is een placeholder voor wanneer echte analytics data wordt toegevoegd.

Draai via:
    docker compose exec api python -m scripts.seed_analytics

Of lokaal:
    python -m scripts.seed_analytics
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Geen analytics data om te seeden — placeholder voor toekomstige data.")
    logger.info("Voeg analytics data toe wanneer beschikbaar.")


if __name__ == "__main__":
    asyncio.run(main())
