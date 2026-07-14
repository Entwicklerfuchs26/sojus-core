#!/usr/bin/env python3
"""Tool-Router für Sojus Core — Keyword-basiertes MCP-Server-Routing.

Dieses Modul ist eine extrahierte, eigenständige Version der Routing-Logik
aus core.py. Noch nicht in core.py eingebunden — erst nach Jonas' OK.

Architektur:
  tool_groups.json  → welche Keywords → welche Server
  tool_tiers.json   → welche Tools brauchen Bestätigung (Tier 2/3)
  ToolRouter.resolve(query) → gefilterte Tool-Liste + tool_map

Erweiterungen gegenüber core.py:
  - Multi-Gruppe: alle passenden Gruppen werden gesammelt (kein break-after-first)
  - Cache-Invalidierung: TTL-basiert (Datei-Änderungen werden erkannt)
  - Fallback-Stufen: Gruppe → Alles
"""

import json
import logging
import os
import time
from typing import Optional

log = logging.getLogger("sojus.tool_router")


class ToolRouter:
    def __init__(
        self,
        mcp_servers: dict[str, str],
        tool_groups_file: str = "/etc/sojus/tool_groups.json",
        tool_tiers_file: str = "/etc/sojus/tool_tiers.json",
        cache_ttl: int = 60,
    ) -> None:
        self._servers = mcp_servers
        self._groups_file = tool_groups_file
        self._tiers_file = tool_tiers_file
        self._cache_ttl = cache_ttl

        self._groups: dict = {}
        self._groups_mtime: float = 0.0
        self._tiers: dict = {}
        self._tiers_mtime: float = 0.0

    # ── Config-Laden mit TTL-Cache ────────────────────────────────────────────

    def _load_groups(self) -> dict:
        try:
            mtime = os.path.getmtime(self._groups_file)
        except OSError:
            return {}
        now = time.monotonic()
        if mtime != self._groups_mtime:
            try:
                with open(self._groups_file) as f:
                    self._groups = json.load(f)
                self._groups_mtime = mtime
                log.debug("tool_groups.json neu geladen")
            except (OSError, json.JSONDecodeError) as e:
                log.warning("tool_groups.json Ladefehler: %s", e)
        return self._groups

    def _load_tiers(self) -> dict:
        try:
            mtime = os.path.getmtime(self._tiers_file)
        except OSError:
            return {}
        if mtime != self._tiers_mtime:
            try:
                with open(self._tiers_file) as f:
                    self._tiers = json.load(f)
                self._tiers_mtime = mtime
                log.debug("tool_tiers.json neu geladen")
            except (OSError, json.JSONDecodeError) as e:
                log.warning("tool_tiers.json Ladefehler: %s", e)
        return self._tiers

    # ── Routing ───────────────────────────────────────────────────────────────

    def resolve_servers(self, query: str) -> set[str]:
        """Gibt die Menge der passenden Server-Namen zurück.

        Unterschied zu core.py: alle passenden Gruppen werden gesammelt,
        nicht nur die erste. Damit kann 'Schick mir eine Push-Nachricht über
        den Kalender' beide Gruppen triggern.
        """
        groups = self._load_groups()
        query_lower = query.lower()
        matched: set[str] = set()

        for group_name, group_data in groups.items():
            if not isinstance(group_data, dict):
                continue
            keywords: list[str] = group_data.get("keywords", [])
            if any(kw in query_lower for kw in keywords):
                new = set(group_data.get("servers", []))
                matched |= new
                log.info("Tool-Router: Gruppe '%s' → %s", group_name, new)

        if not matched:
            log.info("Tool-Router: kein Keyword-Treffer → alle Server")
            return set(self._servers.keys())

        # Nur bekannte Server zurückgeben
        return matched & set(self._servers.keys())

    # ── Tier-Klassifikation ───────────────────────────────────────────────────

    def tier(self, tool_name: str) -> int:
        """1=lesen, 2=schreibend, 3=destruktiv."""
        tiers = self._load_tiers()
        name = tool_name.lower()
        for pattern in tiers.get("tier3_patterns", []):
            if pattern.lower() in name:
                return 3
        for pattern in tiers.get("tier2_patterns", []):
            if pattern.lower() in name:
                return 2
        return 1

    # ── Server-URL ────────────────────────────────────────────────────────────

    def url(self, server: str) -> Optional[str]:
        return self._servers.get(server)
