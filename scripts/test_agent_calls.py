"""
Simulates different agent scenarios querying the brein.

Draai via:
    docker compose exec api python -m scripts.test_agent_calls

Vereist: een draaiende API op localhost:8000 met seed data geladen.
"""

import asyncio
import json
import sys

import httpx

BASE_URL = "http://localhost:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        print("=" * 60)
        print("UPPR Digitaal Brein — Agent Simulation Tests")
        print("=" * 60)

        # Check health first
        r = await client.get("/health")
        if r.status_code != 200:
            print(f"FAIL: Health check returned {r.status_code}")
            sys.exit(1)
        print(f"\nHealth: {r.json()}\n")

        # ------------------------------------------------------------------
        # Scenario 1: Company Knowledge Agent
        # ------------------------------------------------------------------
        print("-" * 60)
        print("Scenario 1: Company Knowledge Agent")
        print("-" * 60)

        r = await client.get("/api/v1/knowledge/company")
        print(f"  GET /knowledge/company → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            for entry in data:
                print(f"    [{entry['type']}] {entry['title']}")

        r = await client.get("/api/v1/knowledge/tone-of-voice")
        print(f"  GET /knowledge/tone-of-voice → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    {data['title']}: {data['content'][:80]}...")

        # ------------------------------------------------------------------
        # Scenario 2: Sales Prospector (scoped)
        # ------------------------------------------------------------------
        print("\n" + "-" * 60)
        print("Scenario 2: Sales Prospector")
        print("-" * 60)

        r = await client.get("/api/v1/knowledge/icp", params={"segment": "vve"})
        print(f"  GET /knowledge/icp?segment=vve → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            for entry in data:
                print(f"    {entry['title']}")

        r = await client.post(
            "/api/v1/contacts/check",
            json={"company_name": "VVE Beheer Amsterdam"},
        )
        print(f"  POST /contacts/check (existing) → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    exists={data['exists']}, contact={data.get('contact', {}).get('company_name')}")

        r = await client.post(
            "/api/v1/contacts/check",
            json={"company_name": "Nieuw Onbekend Bedrijf BV"},
        )
        print(f"  POST /contacts/check (new) → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    exists={data['exists']}")

        # ------------------------------------------------------------------
        # Scenario 3: Analyst Agent
        # ------------------------------------------------------------------
        print("\n" + "-" * 60)
        print("Scenario 3: Analyst Agent")
        print("-" * 60)

        r = await client.post(
            "/api/v1/brain/query",
            json={
                "query": "Hoe presteren we bij VVE-beheerders?",
                "agent_id": "analyst_agent",
            },
        )
        print(f"  POST /brain/query → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    strategy: {data['strategy']}")
            print(f"    results: {len(data['results'])} chunks")
            for result in data["results"][:3]:
                print(f"      [{result['entry_type']}] {result['entry_title']}: score={result['score']}")

        # ------------------------------------------------------------------
        # Scenario 4: Content Agent (semantic search)
        # ------------------------------------------------------------------
        print("\n" + "-" * 60)
        print("Scenario 4: Content Agent")
        print("-" * 60)

        r = await client.post(
            "/api/v1/semantic/search",
            json={"query": "tone of voice voor LinkedIn posts", "top_k": 3},
        )
        print(f"  POST /semantic/search → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    results: {data['total']} chunks")
            for result in data["results"]:
                print(f"      [{result['entry_type']}] {result['entry_title']}: score={result['score']}")

        # ------------------------------------------------------------------
        # Scenario 5: Data Query (structured)
        # ------------------------------------------------------------------
        print("\n" + "-" * 60)
        print("Scenario 5: Data Query (structured)")
        print("-" * 60)

        r = await client.get(
            "/api/v1/structured/query",
            params={"metric_type": "deal"},
        )
        print(f"  GET /structured/query?metric_type=deal → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    total records: {data['total']}")
            print(f"    aggregation: {json.dumps(data['aggregation'])}")

        # ------------------------------------------------------------------
        # Scenario 6: List all services
        # ------------------------------------------------------------------
        print("\n" + "-" * 60)
        print("Scenario 6: Services")
        print("-" * 60)

        r = await client.get("/api/v1/knowledge/services")
        print(f"  GET /knowledge/services → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            for entry in data:
                print(f"    {entry['title']}")

        r = await client.get("/api/v1/knowledge/services", params={"segment": "schilder"})
        print(f"  GET /knowledge/services?segment=schilder → {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    filtered: {len(data)} services")

        print("\n" + "=" * 60)
        print("All scenarios completed.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
