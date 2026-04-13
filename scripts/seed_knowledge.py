"""
Seed script: vul het brein met testdata.

Draai via:
    docker compose exec api python -m scripts.seed_knowledge

Of lokaal:
    python -m scripts.seed_knowledge
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.models import Contact, KnowledgeChunk, KnowledgeEntry
from src.embeddings.chunking import ChunkingService
from src.embeddings.service import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vul hier je eigen content in — voorbeelden hieronder zijn placeholders.
# Types: bedrijfsprofiel, propositie, icp, dienst, tone_of_voice, werkwijze, overig
# ---------------------------------------------------------------------------

KNOWLEDGE_ENTRIES = [
    # --- Bedrijfsprofiel ---
    {
        "type": "bedrijfsprofiel",
        "title": "Bedrijfsprofiel — Novaflow Digital",
        "content": (
            "Novaflow Digital is een digitaal bureau gevestigd in Amsterdam, opgericht in 2019. "
            "We helpen middelgrote en grote organisaties met digitale transformatie, van strategie tot implementatie.\n\n"
            "## Missie\n"
            "Complexe technologie toegankelijk maken voor ambitieuze organisaties.\n\n"
            "## Kernwaarden\n"
            "- **Transparantie** — eerlijk communiceren over mogelijkheden en beperkingen\n"
            "- **Vakmanschap** — kwaliteit boven snelheid, maar liefst allebei\n"
            "- **Partnerschap** — langdurige relaties boven eenmalige projecten\n\n"
            "## Team\n"
            "Het team bestaat uit 35 medewerkers: developers, designers, strategists en data-engineers. "
            "We werken in multidisciplinaire squads van 4-6 personen per klant."
        ),
    },
    # --- Propositie ---
    {
        "type": "propositie",
        "title": "Kernpropositie Novaflow",
        "content": (
            "Wij bouwen digitale producten die organisaties laten groeien. "
            "Van webplatformen en apps tot AI-gedreven tools — we combineren design, technologie en data "
            "om oplossingen te maken die écht werken.\n\n"
            "Onze belofte: je krijgt een team dat meedenkt, niet alleen uitvoert. "
            "We challengen briefings, denken in uitkomsten en leveren werkende software — geen dikke rapporten."
        ),
    },
    # --- ICP's ---
    {
        "type": "icp",
        "title": "ICP — Scale-up (50-200 medewerkers)",
        "content": (
            "## Profiel\n"
            "Snelgroeiende B2B SaaS scale-ups met 50-200 medewerkers, Series A/B funding, "
            "gevestigd in Nederland of DACH-regio.\n\n"
            "## Pijnpunten\n"
            "- Technische schuld door snelle groei — het MVP is een productie-nachtmerrie geworden\n"
            "- Geen interne designcapaciteit voor de volgende fase\n"
            "- Moeten internationaliseren maar platform is niet klaar\n"
            "- Data zit in silo's, geen overzicht over klantgedrag\n\n"
            "## Budget & besluitvorming\n"
            "- Typisch projectbudget: €80K-250K\n"
            "- Beslisser: CTO of VP Engineering, met buy-in van CEO\n"
            "- Salescyclus: 4-8 weken\n\n"
            "## Wat ze zoeken\n"
            "Een partner die hun taal spreekt, snel kan schakelen en kwaliteit levert zonder enterprise-overhead."
        ),
    },
    {
        "type": "icp",
        "title": "ICP — Corporate innovatieteam",
        "content": (
            "## Profiel\n"
            "Innovatie- of digitaliserings-afdelingen binnen grote corporates (500+ medewerkers), "
            "veelal in financial services, energie of gezondheidszorg.\n\n"
            "## Pijnpunten\n"
            "- Interne IT is traag en risico-avers\n"
            "- Moeten snel prototypen maar zitten vast in procurement-processen\n"
            "- Willen AI inzetten maar weten niet waar te beginnen\n"
            "- Moeten resultaten laten zien aan board binnen 6 maanden\n\n"
            "## Budget & besluitvorming\n"
            "- Typisch projectbudget: €150K-500K\n"
            "- Beslisser: Head of Innovation of CDO, met procurement gate\n"
            "- Salescyclus: 8-16 weken (incl. procurement)\n\n"
            "## Wat ze zoeken\n"
            "Bewezen trackrecord, security compliance, en een team dat zowel kan prototypen als productionaliseren."
        ),
    },
    # --- Diensten ---
    {
        "type": "dienst",
        "title": "Platform Development",
        "content": (
            "## Omschrijving\n"
            "We bouwen schaalbare webplatformen en applicaties op maat. "
            "Van greenfield builds tot het moderniseren van legacy systemen.\n\n"
            "## Technologie\n"
            "- Frontend: React, Next.js, TypeScript\n"
            "- Backend: Python (FastAPI, Django), Node.js\n"
            "- Infra: AWS, Vercel, Docker, Terraform\n"
            "- Database: PostgreSQL, Redis, Elasticsearch\n\n"
            "## Werkwijze\n"
            "Sprints van 2 weken met demo's. Dedicated squad per klant. "
            "CI/CD pipeline vanaf dag 1. Wekelijkse sync met stakeholders.\n\n"
            "## Prijsindicatie\n"
            "€100-180/uur afhankelijk van senioriteit. Typisch project: 3-9 maanden."
        ),
    },
    {
        "type": "dienst",
        "title": "AI & Data Solutions",
        "content": (
            "## Omschrijving\n"
            "We helpen organisaties AI en data praktisch inzetten. "
            "Van chatbots en kennisbanken tot predictive analytics en procesautomatisering.\n\n"
            "## Aanbod\n"
            "- **AI Assistenten** — domeinspecifieke chatbots met RAG (retrieval-augmented generation)\n"
            "- **Data Pipelines** — van ruwe data naar bruikbare inzichten\n"
            "- **Computer Vision** — beeldherkenning voor kwaliteitscontrole of documentverwerking\n"
            "- **Automatisering** — procesflows met AI-in-the-loop\n\n"
            "## Aanpak\n"
            "We starten altijd met een 2-weekse Discovery: begrijpen van de use case, data-audit, "
            "en een werkend proof-of-concept. Pas daarna schalen we op.\n\n"
            "## Prijsindicatie\n"
            "Discovery: €15K-25K. Implementatie: €50K-200K afhankelijk van scope."
        ),
    },
    {
        "type": "dienst",
        "title": "Design & UX",
        "content": (
            "## Omschrijving\n"
            "Product design van research tot pixel-perfect UI. "
            "We ontwerpen interfaces die gebruikers begrijpen en graag gebruiken.\n\n"
            "## Aanbod\n"
            "- User research & testing\n"
            "- UX strategie & information architecture\n"
            "- UI design (Figma) met design system\n"
            "- Prototyping & validatie\n\n"
            "## Werkwijze\n"
            "Design en development lopen parallel — geen waterval. "
            "Designers zitten in hetzelfde squad als developers.\n\n"
            "## Prijsindicatie\n"
            "€110-160/uur. Design sprint (5 dagen): €12K-18K."
        ),
    },
    # --- Tone of Voice ---
    {
        "type": "tone_of_voice",
        "title": "Tone of Voice — Novaflow",
        "content": (
            "## Kernprincipes\n"
            "- **Direct en helder** — geen jargon tenzij de ontvanger het verwacht\n"
            "- **Zelfverzekerd maar niet arrogant** — we weten wat we doen, maar luisteren eerst\n"
            "- **Informeel professioneel** — je/jij, geen u. Maar wel serieus over het werk\n"
            "- **Concreet** — altijd voorbeelden, cijfers of referenties. Geen vage beloftes\n\n"
            "## Schrijfregels\n"
            "- Korte zinnen. Max 20 woorden per zin als het kan.\n"
            "- Actieve vorm ('wij bouwen') niet passief ('er wordt gebouwd')\n"
            "- Vermijd: 'innovatief', 'synergie', 'uniek', 'state-of-the-art', 'cutting-edge'\n"
            "- Wel gebruiken: concrete resultaten, technische details, eerlijke nuance\n\n"
            "## Per kanaal\n"
            "- **Website**: inspirerend maar bondig. Laat het werk spreken.\n"
            "- **Email/sales**: persoonlijk, to-the-point. Geen templates.\n"
            "- **LinkedIn**: thought leadership met een mening. Niet alleen delen, ook stelling nemen.\n"
            "- **Technische docs**: helder, gestructureerd, met codevoorbeelden."
        ),
    },
    # --- Werkwijze ---
    {
        "type": "werkwijze",
        "title": "Werkwijze — Hoe we projecten aanpakken",
        "content": (
            "## Fase 1: Discovery (1-2 weken)\n"
            "Stakeholder interviews, technische audit, user research. Resultaat: projectbrief met scope, "
            "risico's en architectuurvoorstel.\n\n"
            "## Fase 2: Foundation (2-4 weken)\n"
            "Opzet development environment, CI/CD, design system basics, data model. "
            "Eerste werkende versie (walking skeleton).\n\n"
            "## Fase 3: Build (6-16 weken)\n"
            "Sprints van 2 weken. Elke sprint een demo. Continu deployen naar staging. "
            "Wekelijkse sync met product owner.\n\n"
            "## Fase 4: Launch & Scale\n"
            "Performance testing, security audit, monitoring setup. Gefaseerde rollout. "
            "Na launch: 4 weken hypercare, daarna overgang naar retainer of overdracht.\n\n"
            "## Principes\n"
            "- Geen big bang launches — altijd iteratief\n"
            "- Transparante communicatie: als iets niet kan, zeggen we het direct\n"
            "- Code is eigendom van de klant, altijd\n"
            "- Documentatie is onderdeel van de Definition of Done"
        ),
    },
]

CONTACTS = [
    {"company_name": "TechFlow BV", "contact_name": "Mark de Vries", "email": "mark@techflow.nl", "source": "crm", "status": "client"},
    {"company_name": "GreenGrid Energy", "contact_name": "Lisa Bakker", "email": "l.bakker@greengrid.eu", "source": "crm", "status": "lead"},
    {"company_name": "MediCore Health", "contact_name": "Dr. Sandra Visser", "email": "s.visser@medicore.nl", "source": "event", "status": "prospect"},
    {"company_name": "FinBridge Capital", "contact_name": "Thomas Smit", "email": "thomas@finbridge.com", "source": "crm", "status": "client"},
    {"company_name": "Logistiq NL", "contact_name": "Peter Janssen", "email": "pjanssen@logistiq.nl", "source": "website", "status": "lead"},
]


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    embedder = EmbeddingService.get_instance()
    chunker = ChunkingService()

    async with session_factory() as session:
        # Seed knowledge entries
        for entry_data in KNOWLEDGE_ENTRIES:
            await _create_entry(session, embedder, chunker, entry_data)

        # Seed contacts
        for contact_data in CONTACTS:
            contact = Contact(**contact_data)
            session.add(contact)

        await session.commit()
        logger.info("Seeded %d knowledge entries and %d contacts", len(KNOWLEDGE_ENTRIES), len(CONTACTS))

    await engine.dispose()


async def _create_entry(
    session: AsyncSession,
    embedder: EmbeddingService,
    chunker: ChunkingService,
    data: dict,
):
    entry = KnowledgeEntry(
        type=data["type"],
        title=data["title"],
        content=data["content"],
        created_by="seed_script",
    )

    # Generate entry embedding
    entry.embedding = await embedder.embed_text(f"{data['title']}\n\n{data['content']}")
    session.add(entry)
    await session.flush()

    # Chunk and embed
    chunk_data = chunker.chunk_with_token_counts(data["type"], data["content"])
    if chunk_data:
        chunk_texts = [c[0] for c in chunk_data]
        chunk_embeddings = await embedder.embed_batch(chunk_texts)

        for i, ((text, token_count), embedding) in enumerate(zip(chunk_data, chunk_embeddings)):
            chunk = KnowledgeChunk(
                entry_id=entry.id,
                chunk_index=i,
                content=text,
                embedding=embedding,
                token_count=token_count,
            )
            session.add(chunk)

    logger.info("Created: [%s] %s (%d chunks)", data["type"], data["title"], len(chunk_data))


if __name__ == "__main__":
    asyncio.run(main())
