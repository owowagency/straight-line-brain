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
# Test content (Dutch, UPPR context)
# ---------------------------------------------------------------------------

KNOWLEDGE_ENTRIES = [
    {
        "type": "bedrijfsprofiel",
        "title": "UPPR — Bedrijfsprofiel",
        "content": (
            "UPPR is een tech-bedrijf dat AI-gedreven software bouwt voor de vastgoedsector. "
            "Onze missie is om vastgoedprofessionals te helpen slimmer te werken door automatisering "
            "en data-gedreven inzichten. We geloven in open technologie, transparantie en het "
            "versterken van menselijke expertise met AI.\n\n"
            "Kernwaarden: innovatie, betrouwbaarheid, klantgerichtheid, transparantie.\n\n"
            "Opgericht in 2024, gevestigd in Nederland."
        ),
    },
    {
        "type": "propositie",
        "title": "UPPR.OS — Propositie",
        "content": (
            "UPPR.OS is een AI-platform dat vastgoedprofessionals ondersteunt bij hun dagelijkse "
            "werkzaamheden. Het platform combineert intelligente agents met bedrijfsspecifieke "
            "kennis om taken te automatiseren.\n\n"
            "## Kernfunctionaliteiten\n"
            "- Automatische lead-kwalificatie en prospecting\n"
            "- Slimme documentverwerking en extractie\n"
            "- Data-analyse en rapportage\n"
            "- Gepersonaliseerde communicatie op basis van tone of voice\n\n"
            "## Waardepropositie\n"
            "Bespaar 10+ uur per week door repetitieve taken te automatiseren. "
            "Verhoog conversie door data-gedreven inzichten. "
            "Behoud je persoonlijke touch dankzij AI die je stijl leert."
        ),
    },
    {
        "type": "icp",
        "title": "ICP — VVE-beheerder",
        "content": (
            "## Profiel\n"
            "VVE-beheerders zijn verantwoordelijk voor het beheer van Verenigingen van Eigenaren. "
            "Ze managen gemiddeld 50-200 VVE's en hebben te maken met onderhoud, financiën en "
            "communicatie met eigenaren.\n\n"
            "## Pijnpunten\n"
            "- Veel administratieve rompslomp en handmatig werk\n"
            "- Moeite met het bijhouden van onderhoudsplanningen\n"
            "- Tijdrovende communicatie met eigenaren\n"
            "- Gebrek aan data-inzichten over hun portefeuille\n\n"
            "## Hoe UPPR.OS helpt\n"
            "- Automatisering van terugkerende communicatie\n"
            "- Slimme onderhoudsplanning op basis van data\n"
            "- Centraal kennisbeheer voor VVE-documenten\n"
            "- Rapportage en inzichten per VVE"
        ),
    },
    {
        "type": "icp",
        "title": "ICP — Woningcorporatie",
        "content": (
            "## Profiel\n"
            "Woningcorporaties beheren grote portefeuilles sociale huurwoningen. "
            "Ze hebben complexe processen voor onderhoud, verhuur en bewonersparticipatie.\n\n"
            "## Pijnpunten\n"
            "- Grote schaal maakt persoonlijke service lastig\n"
            "- Verouderde systemen en data-silo's\n"
            "- Druk op verduurzaming en rapportage\n"
            "- Behoefte aan betere bewonercommunicatie\n\n"
            "## Hoe UPPR.OS helpt\n"
            "- Schaalbare AI-gestuurde bewonercommunicatie\n"
            "- Integratie met bestaande systemen via API's\n"
            "- Data-analyse over de hele portefeuille\n"
            "- Automatische rapportage voor toezichthouders"
        ),
    },
    {
        "type": "icp",
        "title": "ICP — Schildersbedrijf",
        "content": (
            "## Profiel\n"
            "Schildersbedrijven werken vaak als onderaannemer voor VVE-beheerders en corporaties. "
            "Ze hebben een klein kantoorteam en veel buitendienstmedewerkers.\n\n"
            "## Pijnpunten\n"
            "- Onvoorspelbare werkstroom en planning\n"
            "- Moeilijk om nieuwe klanten te vinden\n"
            "- Offerteproces is tijdrovend\n"
            "- Weinig online zichtbaarheid\n\n"
            "## Hoe UPPR.OS helpt\n"
            "- Automatische lead-generatie via VVE-netwerk\n"
            "- Slimme offertetool met historische data\n"
            "- Planning-optimalisatie\n"
            "- Online profiel en referenties"
        ),
    },
    {
        "type": "dienst",
        "title": "Dienst — AI Prospecting Agent",
        "content": (
            "## Beschrijving\n"
            "De AI Prospecting Agent identificeert automatisch potentiële klanten op basis van "
            "het ICP-profiel en publiek beschikbare data.\n\n"
            "## Features\n"
            "- Automatische bedrijfsidentificatie via KVK en web scraping\n"
            "- Lead scoring op basis van ICP-match\n"
            "- Deduplicatie tegen bestaande CRM-data\n"
            "- Gepersonaliseerde outreach-suggesties\n\n"
            "## Geschikt voor\n"
            "Sales teams die hun pipeline willen vullen zonder handmatig te zoeken."
        ),
    },
    {
        "type": "dienst",
        "title": "Dienst — Document Intelligence",
        "content": (
            "## Beschrijving\n"
            "Automatische verwerking en extractie van informatie uit vastgoeddocumenten.\n\n"
            "## Features\n"
            "- PDF/DOCX parsing en tekst-extractie\n"
            "- Slimme samenvatting van lange documenten\n"
            "- Entiteit-extractie (bedragen, data, partijen)\n"
            "- Doorzoekbaar archief met semantische search"
        ),
    },
    {
        "type": "dienst",
        "title": "Dienst — Sales Analytics Dashboard",
        "content": (
            "## Beschrijving\n"
            "Real-time inzichten in sales performance met AI-gegenereerde analyses.\n\n"
            "## Features\n"
            "- Pipeline-analyse per segment en product\n"
            "- Conversie-tracking en voorspellingen\n"
            "- Automatische kwartaalrapportages\n"
            "- Vergelijking met historische periodes"
        ),
    },
    {
        "type": "dienst",
        "title": "Dienst — Content Generator",
        "content": (
            "## Beschrijving\n"
            "AI-gestuurde content creatie die aansluit bij de tone of voice van het bedrijf.\n\n"
            "## Features\n"
            "- LinkedIn posts en artikelen\n"
            "- E-mail templates voor sales en marketing\n"
            "- Presentatie-content en one-pagers\n"
            "- Consistente tone of voice over alle kanalen"
        ),
    },
    {
        "type": "dienst",
        "title": "Dienst — Klant Onboarding Assistent",
        "content": (
            "## Beschrijving\n"
            "Geautomatiseerd onboarding-proces voor nieuwe klanten.\n\n"
            "## Features\n"
            "- Stapsgewijs onboarding-plan\n"
            "- Automatische data-import uit bestaande systemen\n"
            "- Kennisbank vullen met klantspecifieke informatie\n"
            "- Voortgang-tracking en check-ins"
        ),
    },
    {
        "type": "tone_of_voice",
        "title": "UPPR Tone of Voice",
        "content": (
            "UPPR communiceert professioneel maar toegankelijk. We zijn niet corporate-stijf, "
            "maar ook niet te casual.\n\n"
            "Richtlijnen:\n"
            "- Gebruik 'je' in plaats van 'u' (tenzij formele context)\n"
            "- Wees concreet en resultaatgericht, vermijd vage beloftes\n"
            "- Gebruik voorbeelden en cijfers waar mogelijk\n"
            "- Toon expertise zonder arrogant te zijn\n"
            "- Gebruik Nederlandse termen tenzij de Engelse term standaard is in de branche\n"
            "- Eindig met een duidelijke call-to-action\n"
            "- Emoji's: spaarzaam, alleen in social media context"
        ),
    },
    {
        "type": "werkwijze",
        "title": "UPPR Werkwijze — Sales Proces",
        "content": (
            "## Stap 1: Prospecting\n"
            "De AI Prospecting Agent identificeert potentiële klanten op basis van het ICP. "
            "Leads worden automatisch gescoord en gedeeld met het sales team.\n\n"
            "## Stap 2: Eerste Contact\n"
            "Sales neemt contact op via gepersonaliseerde e-mail of LinkedIn. "
            "De Content Generator helpt bij het opstellen van berichten.\n\n"
            "## Stap 3: Discovery Call\n"
            "Tijdens het eerste gesprek worden behoeften en pijnpunten in kaart gebracht. "
            "Notities worden automatisch verwerkt en opgeslagen in het brein.\n\n"
            "## Stap 4: Demo & Voorstel\n"
            "Op basis van de discovery wordt een gepersonaliseerde demo voorbereid. "
            "Het voorstel wordt gegenereerd met relevante case studies en ROI-berekeningen.\n\n"
            "## Stap 5: Closing & Onboarding\n"
            "Na akkoord start het onboarding-proces via de Klant Onboarding Assistent. "
            "Het klantprofiel wordt aangemaakt in het brein."
        ),
    },
]

CONTACTS = [
    {"company_name": "VVE Beheer Amsterdam", "contact_name": "Jan de Vries", "email": "jan@vvebeheer-adam.nl", "source": "salesforce", "status": "client"},
    {"company_name": "Woonstad Rotterdam", "contact_name": "Maria Jansen", "email": "m.jansen@woonstad.nl", "source": "salesforce", "status": "client"},
    {"company_name": "De Schildersmeesters", "contact_name": "Pieter Bakker", "email": "pieter@schildersmeesters.nl", "source": "agent_discovered", "status": "lead"},
    {"company_name": "VVE Plus", "contact_name": "Sophie van Dam", "email": "sophie@vveplus.nl", "source": "salesforce", "status": "prospect"},
    {"company_name": "Corporatie Zuid", "contact_name": "Ahmed El Amrani", "email": "a.elamrani@corporatiezuid.nl", "source": "manual", "status": "prospect"},
    {"company_name": "Vastgoed Centraal", "contact_name": "Lotte Vermeer", "email": "lotte@vastgoedcentraal.nl", "source": "agent_discovered", "status": "lead"},
    {"company_name": "Schilder & Zo", "contact_name": "Henk Smit", "email": "henk@schilderenzo.nl", "source": "salesforce", "status": "churned"},
    {"company_name": "VVE Management Nederland", "contact_name": "Karin de Boer", "email": "k.deboer@vvemnl.nl", "source": "salesforce", "status": "client"},
    {"company_name": "Woonstichting Eigen Haard", "contact_name": "Thomas Mulder", "email": "t.mulder@eigenhaard.nl", "source": "manual", "status": "prospect"},
    {"company_name": "Pro Paint Services", "contact_name": "Rick van Leeuwen", "email": "rick@propaint.nl", "source": "agent_discovered", "status": "lead"},
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
