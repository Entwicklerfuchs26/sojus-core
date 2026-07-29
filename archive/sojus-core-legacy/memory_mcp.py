#!/usr/bin/env python3
"""Sojus Memory MCP Server — Port 8010
Langzeitgedächtnis für Jonas. Fakten lesen, schreiben, suchen, löschen.
"""

import os
import json
import uuid
from datetime import datetime
from fastmcp import FastMCP

MEMORY_FILE = os.getenv("MEMORY_FILE", "/etc/sojus/memory.json")

mcp = FastMCP(
    "fuchs-sojus-memory",
    instructions="Sojus Langzeitgedächtnis auf darwin26. Persistente Fakten über Jonas lesen, schreiben und durchsuchen.",
)


def _load() -> list[dict]:
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(facts: list[dict]) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)


@mcp.tool()
def memory_read() -> list[dict]:
    """Alle gespeicherten Fakten über Jonas lesen."""
    return _load()


@mcp.tool()
def memory_write(fact: str) -> dict:
    """Einen neuen Fakt über Jonas dauerhaft speichern.

    NUR explizite persönliche Fakten speichern:
    ✅ Präferenzen, Gewohnheiten, laufende Projekte, wichtige Personen, Entscheidungen
    ❌ NICHT: Tool-Ergebnisse, Gesprächsinhalte, temporäre Informationen, Vermutungen
    """
    facts = _load()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "fact": fact,
        "created": datetime.now().isoformat(),
    }
    facts.append(entry)
    _save(facts)
    return {"success": True, "id": entry["id"], "fact": fact}


@mcp.tool()
def memory_search(query: str) -> list[dict]:
    """Im Gedächtnis nach Fakten suchen (case-insensitive Substring-Suche)."""
    facts = _load()
    q = query.lower()
    return [f for f in facts if q in f.get("fact", "").lower()]


@mcp.tool()
def memory_delete(fact_id: str) -> dict:
    """Einen gespeicherten Fakt anhand seiner ID löschen."""
    facts = _load()
    before = len(facts)
    facts = [f for f in facts if f.get("id") != fact_id]
    if len(facts) < before:
        _save(facts)
        return {"success": True, "deleted_id": fact_id}
    return {"success": False, "error": f"Fakt mit ID '{fact_id}' nicht gefunden"}


@mcp.tool()
def memory_update(fact_id: str, new_fact: str) -> dict:
    """Einen bestehenden Fakt aktualisieren."""
    facts = _load()
    for f in facts:
        if f.get("id") == fact_id:
            f["fact"] = new_fact
            f["updated"] = datetime.now().isoformat()
            _save(facts)
            return {"success": True, "id": fact_id, "fact": new_fact}
    return {"success": False, "error": f"Fakt mit ID '{fact_id}' nicht gefunden"}


@mcp.tool()
def memory_clear_all() -> dict:
    """ALLE Fakten löschen. Nur auf explizite Anfrage von Jonas verwenden."""
    count = len(_load())
    _save([])
    return {"success": True, "deleted_count": count}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8010)
