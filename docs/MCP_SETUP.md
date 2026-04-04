# MCP Server Setup — UPPR Digitaal Brein

Het Digitaal Brein kan als MCP server worden gebruikt met Claude Code en Claude Desktop.

## Vereisten

1. Het Digitaal Brein draait (via Docker Compose)
2. Python 3.12+ met `mcp` en `httpx` geïnstalleerd
3. Seed data geladen

```bash
# Start het brein
cd /pad/naar/Digitaal_Brein
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic revision --autogenerate -m "initial"
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_knowledge
docker compose exec api python -m scripts.seed_analytics
```

## Optie 1: Claude Code (CLI)

Voeg toe aan je project's `.mcp.json` (in de root van je project):

```json
{
  "mcpServers": {
    "digitaal-brein": {
      "command": "python",
      "args": ["/pad/naar/Digitaal_Brein/mcp_server.py"],
      "env": {
        "BREIN_URL": "http://localhost:8000",
        "BREIN_API_KEY": ""
      }
    }
  }
}
```

Of globaal in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "digitaal-brein": {
      "command": "python",
      "args": ["/pad/naar/Digitaal_Brein/mcp_server.py"],
      "env": {
        "BREIN_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Optie 2: Claude Desktop

Voeg toe aan je Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` op macOS):

```json
{
  "mcpServers": {
    "digitaal-brein": {
      "command": "python",
      "args": ["/pad/naar/Digitaal_Brein/mcp_server.py"],
      "env": {
        "BREIN_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Environment variabelen

| Variabele | Standaard | Beschrijving |
|-----------|-----------|-------------|
| `BREIN_URL` | `http://localhost:8000` | URL van de Brein API |
| `BREIN_API_KEY` | (leeg) | API key voor authenticatie (optioneel) |

## Beschikbare tools

Na registratie heeft Claude toegang tot deze tools:

### Retrieval
| Tool | Beschrijving |
|------|-------------|
| `get_company_profile` | Bedrijfsprofiel + propositie |
| `get_icp_profile` | ICP per segment (VVE, corporatie, schilder) |
| `get_tone_of_voice` | Tone of voice richtlijnen |
| `get_services` | Diensten, optioneel per segment |
| `search_knowledge` | Semantische vector search |
| `query_brain` | Vrije vraag → automatische routering |
| `check_contact` | Contact deduplicatie |
| `query_analytics` | Analytische data met aggregatie |

### Knowledge Management
| Tool | Beschrijving |
|------|-------------|
| `list_knowledge_entries` | Lijst entries met filters |
| `get_knowledge_entry` | Specifieke entry ophalen |
| `create_knowledge_entry` | Nieuwe entry aanmaken |
| `update_knowledge_entry` | Entry updaten |
| `delete_knowledge_entry` | Entry soft-deleten |

### Ingest
| Tool | Beschrijving |
|------|-------------|
| `ingest_analytics` | Analytische data pushen (bulk) |
| `summarize_analytics` | Samenvatting genereren voor periode |

### Admin
| Tool | Beschrijving |
|------|-------------|
| `list_agent_scopes` | Agent permissies bekijken |
| `list_registry_proposals` | Endpoint-voorstellen |
| `list_active_endpoints` | Actieve dynamische endpoints |
| `detect_query_patterns` | Terugkerende patronen detecteren |

## Testen

Na configuratie kun je het testen in Claude Code:

```
> Wat is het bedrijfsprofiel van UPPR?
> Wat is het ICP voor VVE-beheerders?
> Zoek in de kennisbank naar "tone of voice voor LinkedIn"
> Hoeveel deals hebben we in Q1 2025?
```

Claude zal automatisch de juiste brein-tools aanroepen.
