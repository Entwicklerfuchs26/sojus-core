#!/usr/bin/env python3
"""Sojus Core — KI-Agent mit MCP-Tools, OpenAI-kompatibler API auf Port 3001"""

import os
import json
import uuid
import re
import random
import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

# ── KONFIGURATION ─────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://192.168.1.40:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
PIPELINE_API_KEY  = os.getenv("PIPELINE_API_KEY", "sojus-pipeline-key")
MEMORY_FILE       = os.getenv("MEMORY_FILE", "/etc/sojus/memory.json")
REMINDERS_FILE    = os.getenv("REMINDERS_FILE", "/etc/sojus/reminders.json")
TOOL_GROUPS_FILE  = os.getenv("TOOL_GROUPS_FILE", "/etc/sojus/tool_groups.json")
TOOL_TIERS_FILE   = os.getenv("TOOL_TIERS_FILE", "/etc/sojus/tool_tiers.json")
PENDING_FILE      = os.getenv("PENDING_FILE", "/etc/sojus/pending.json")
HA_URL            = os.getenv("HA_URL", "http://127.0.0.1:8123")
HA_TOKEN          = os.getenv("HA_TOKEN", "")
HA_NOTIFY_TARGET  = os.getenv("HA_NOTIFY_TARGET", "mobile_app_iphone_von_jonas")

PENDING_TIMEOUT_SECONDS = 600  # 10 Minuten

MCP_SERVERS: dict[str, str] = {
    "nextcloud":               "http://127.0.0.1:8000/mcp",
    "nextcloud-supplement":    "http://127.0.0.1:8001/mcp",
    "fuchs-openproject":       "http://127.0.0.1:8002/mcp",
    "fuchs-vikunja":           "http://127.0.0.1:8003/mcp",
    "fuchs-homeassistant":     "http://127.0.0.1:8004/mcp",
    "fuchs-n8n":               "http://127.0.0.1:8005/mcp",
    "fuchs-jellyfin":          "http://127.0.0.1:8006/mcp",
    "fuchs-immich":            "http://127.0.0.1:8007/mcp",
    "fuchs-anilist":           "http://127.0.0.1:8008/mcp",
    "fuchs-nextcloud-private": "http://127.0.0.1:8009/mcp",
    "fuchs-sojus-memory":      "http://127.0.0.1:8010/mcp",
    "fuchs-discord":           "http://127.0.0.1:8011/mcp",
    "fuchs-shell":             "http://192.168.1.40:8012/mcp",
    "fuchs-email":             "http://127.0.0.1:8013/mcp",
}

log = logging.getLogger("sojus-core")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── SICHERHEIT — INPUT ────────────────────────────────────────────────────────

_INJECTION_RE = re.compile(
    r"ignore\s+(all\s+)?(previous|above)\s+instructions"
    r"|jailbreak"
    r"|you\s+are\s+now\b"
    r"|pretend\s+(to\s+be|you\s+are)"
    r"|dan\s+mode"
    r"|developer\s+mode"
    r"|override\s+(your\s+|all\s+)?instructions"
    r"|forget\s+(your\s+|all\s+)?instructions"
    r"|act\s+as\s+(if\s+)?you\s+(are|were)"
    r"|new\s+persona",
    re.IGNORECASE,
)

_HARD_BLOCK_RE = re.compile(
    r"rm\s+-[rRfF]*f\s+/"
    r"|dd\s+if=/dev/(zero|random).*of=/dev/"
    r"|mkfs\."
    r"|:\(\)\{.*:\|:",
    re.IGNORECASE | re.DOTALL,
)

_CONFIRM_WORDS = frozenset({"ja", "yes", "bestätigen", "confirm", "ok", "okay", "j", "yep", "yup"})
_CANCEL_WORDS  = frozenset({"nein", "no", "nope", "abbrechen", "cancel", "stop", "n"})


def check_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def check_hard_block(text: str) -> bool:
    return bool(_HARD_BLOCK_RE.search(text))


def is_confirmation(text: str) -> bool:
    return text.strip().lower() in _CONFIRM_WORDS


def is_cancellation(text: str) -> bool:
    return text.strip().lower() in _CANCEL_WORDS


# ── SICHERHEIT — TOOL TIERS ───────────────────────────────────────────────────

_tool_tiers_cache: dict = {}


def _load_tool_tiers() -> dict:
    global _tool_tiers_cache
    if not _tool_tiers_cache:
        try:
            with open(TOOL_TIERS_FILE) as f:
                _tool_tiers_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _tool_tiers_cache = {}
    return _tool_tiers_cache


def tool_tier(tool_name: str) -> int:
    """Gibt Sicherheits-Tier zurück: 1=lesen, 2=schreibend, 3=destruktiv/Shell-Execute."""
    tiers = _load_tool_tiers()
    name = tool_name.lower()
    for pattern in tiers.get("tier3_patterns", []):
        if pattern.lower() in name:
            return 3
    for pattern in tiers.get("tier2_patterns", []):
        if pattern.lower() in name:
            return 2
    return 1


# ── PENDING CONFIRMATION SYSTEM ───────────────────────────────────────────────

def load_pending() -> dict | None:
    try:
        with open(PENDING_FILE) as f:
            data = json.load(f)
        if not data or "actions" not in data:
            return None
        created = datetime.fromisoformat(data.get("created", "2000-01-01"))
        if (datetime.now() - created).total_seconds() > PENDING_TIMEOUT_SECONDS:
            clear_pending()
            return None
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_pending(actions: list[dict], max_tier: int) -> dict:
    code = f"CONFIRM-{random.randint(1000, 9999)}" if max_tier >= 3 else None
    data: dict[str, Any] = {
        "actions":      actions,
        "max_tier":     max_tier,
        "confirm_code": code,
        "created":      datetime.now().isoformat(),
    }
    with open(PENDING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def clear_pending() -> None:
    try:
        with open(PENDING_FILE, "w") as f:
            f.write("{}")
    except OSError:
        pass


def format_confirmation_request(pending: dict) -> str:
    actions  = pending["actions"]
    max_tier = pending.get("max_tier", 2)

    lines = ["**Bestätigung erforderlich** — ich möchte Folgendes tun:\n"]
    for i, a in enumerate(actions, 1):
        tier_label = "🔴 destruktiv/Shell" if a.get("tier", 2) >= 3 else "✏️ schreibend"
        lines.append(f"{i}. `{a['tool']}` ({tier_label})")
        if a.get("arguments"):
            preview = {k: str(v)[:80] for k, v in list(a["arguments"].items())[:3]}
            lines.append(f"   → {json.dumps(preview, ensure_ascii=False)}")

    if max_tier >= 3:
        code = pending["confirm_code"]
        lines.append(
            f"\n🔐 **Tier 3 — systemkritisch.** Gib zur Bestätigung exakt diesen Code ein: `{code}`"
        )
    else:
        lines.append("\nAntwort mit **ja** zum Ausführen, oder **nein** zum Abbrechen.")

    return "\n".join(lines)


async def execute_pending(pending: dict) -> str:
    results: list[str] = []
    for action in pending["actions"]:
        try:
            result = await mcp_call_tool(
                action["server"], action["url"], action["tool"], action["arguments"]
            )
            results.append(f"✅ `{action['tool']}`: {result[:300]}")
            log.info("Pending ausgeführt: %s", action["tool"])
        except Exception as e:
            results.append(f"❌ `{action['tool']}` fehlgeschlagen: {e}")
            log.error("Pending fehlgeschlagen: %s — %s", action["tool"], e)
    clear_pending()
    return "\n".join(results)


# ── GEDÄCHTNIS ────────────────────────────────────────────────────────────────

def load_memory() -> list[dict]:
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_memory(facts: list[dict]) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)


def memory_context(facts: list[dict]) -> str:
    if not facts:
        return ""
    lines = ["## Was Sojus über Jonas weiß:"]
    for f in facts:
        lines.append(f"- {f.get('fact', str(f))}")
    return "\n".join(lines)


# ── MCP CLIENT ────────────────────────────────────────────────────────────────

_mcp_sessions:    dict[str, str]        = {}
_mcp_tools_cache: dict[str, list[dict]] = {}
_mcp_status:      dict[str, bool]       = {}
_mcp_status_ts:   float                 = 0.0


async def _mcp_request(
    url: str,
    method: str,
    params: dict | None = None,
    session_id: str | None = None,
    timeout: int = 30,
) -> tuple[dict, str | None]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["mcp-session-id"] = session_id

    result: dict = {}
    new_sid: str | None = session_id

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", url, json=payload, headers=headers, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                new_sid = resp.headers.get("mcp-session-id", session_id)
                ct = resp.headers.get("content-type", "")

                if "event-stream" in ct:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            msg = json.loads(data_str)
                            if "result" in msg or "error" in msg:
                                result = msg
                        except json.JSONDecodeError:
                            pass
                else:
                    body = await resp.aread()
                    try:
                        result = json.loads(body)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        log.debug("MCP [%s %s]: %s", url, method, e)

    return result, new_sid


async def _mcp_ensure_session(server: str, url: str) -> str | None:
    if server in _mcp_sessions:
        return _mcp_sessions[server]
    resp, sid = await _mcp_request(url, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "sojus-core", "version": "1.0"},
    })
    if sid:
        _mcp_sessions[server] = sid
    return sid


async def mcp_list_tools(server: str, url: str) -> list[dict]:
    if server in _mcp_tools_cache:
        return _mcp_tools_cache[server]
    sid = await _mcp_ensure_session(server, url)
    resp, _ = await _mcp_request(url, "tools/list", {}, session_id=sid, timeout=15)
    tools: list[dict] = resp.get("result", {}).get("tools", [])
    _mcp_tools_cache[server] = tools
    log.info("MCP %s: %d Tools geladen", server, len(tools))
    return tools


async def mcp_call_tool(server: str, url: str, tool_name: str, arguments: dict) -> str:
    sid = await _mcp_ensure_session(server, url)
    resp, _ = await _mcp_request(
        url, "tools/call",
        {"name": tool_name, "arguments": arguments},
        session_id=sid,
        timeout=60,
    )
    if "error" in resp:
        return f"Fehler: {resp['error'].get('message', resp['error'])}"
    content = resp.get("result", {}).get("content", [])
    if isinstance(content, list):
        return "\n".join(
            c.get("text", json.dumps(c, ensure_ascii=False)) if isinstance(c, dict) else str(c)
            for c in content
        )
    return str(content)


# ── TOOL ROUTER ───────────────────────────────────────────────────────────────

_tool_groups: dict = {}


def _load_tool_groups() -> dict:
    global _tool_groups
    if not _tool_groups:
        try:
            with open(TOOL_GROUPS_FILE) as f:
                _tool_groups = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return _tool_groups


async def _fetch_server_tools(server: str, url: str) -> list[dict]:
    try:
        return await mcp_list_tools(server, url)
    except Exception as e:
        log.warning("MCP %s nicht erreichbar: %s", server, e)
        return []


async def get_tools_for_query(query: str) -> tuple[list[dict], dict[str, tuple[str, str]]]:
    """Gibt (openai_tools_list, {tool_name: (server, url)}) zurück."""
    groups = _load_tool_groups()
    query_lower = query.lower()

    matched_servers: set[str] | None = None
    for group_name, group_data in groups.items():
        if not isinstance(group_data, dict):
            continue
        keywords: list[str] = group_data.get("keywords", [])
        if any(kw in query_lower for kw in keywords):
            matched_servers = set(group_data.get("servers", []))
            log.info("Tool-Router: Gruppe '%s' → %s", group_name, matched_servers)
            break

    servers_to_query = matched_servers if matched_servers else set(MCP_SERVERS.keys())

    tasks = [_fetch_server_tools(s, MCP_SERVERS[s]) for s in servers_to_query if s in MCP_SERVERS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    openai_tools: list[dict] = []
    tool_map: dict[str, tuple[str, str]] = {}
    seen_names: set[str] = set()

    for server, tool_list in zip(servers_to_query, results):
        if isinstance(tool_list, Exception) or not isinstance(tool_list, list):
            continue
        url = MCP_SERVERS.get(server, "")
        for tool in tool_list:
            name: str = tool.get("name", "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                },
            })
            tool_map[name] = (server, url)

    return openai_tools, tool_map


async def execute_mcp_tool(
    tool_name: str,
    arguments: dict,
    tool_map: dict[str, tuple[str, str]],
    pending: list[dict],
) -> str:
    """Führt ein MCP-Tool aus — oder merkt es vor wenn Tier 2/3."""
    if check_hard_block(json.dumps(arguments)):
        return "⛔ Aktion durch Sicherheitssystem blockiert."
    if tool_name not in tool_map:
        return f"Tool '{tool_name}' nicht gefunden."

    server, url = tool_map[tool_name]
    tier = tool_tier(tool_name)

    if tier >= 2:
        pending.append({
            "tool":      tool_name,
            "arguments": arguments,
            "server":    server,
            "url":       url,
            "tier":      tier,
        })
        log.info("Tier %d — vorgemerkt: %s", tier, tool_name)
        return f"[Vorgemerkt zur Bestätigung: {tool_name}]"

    log.info("Tool ausführen: %s @ %s", tool_name, server)
    return await mcp_call_tool(server, url, tool_name, arguments)


# ── MODEL ROUTER ──────────────────────────────────────────────────────────────

_COMPLEX_RE = re.compile(
    r"analysier|erkl[äa]r|schreib\s+(?:mir\s+)?(?:einen?|eine)\b|ausf[üu]hrlich"
    r"|detailliert|komplex|plan\b|programm|code\b"
    r"|explain\b|analyz|write\b|create\b",
    re.IGNORECASE,
)


def route_model(message: str) -> str:
    force = os.getenv("FORCE_BACKEND", "").lower()
    if force == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic"
    if force == "ollama":
        return "ollama"
    if not ANTHROPIC_API_KEY:
        return "ollama"
    if len(message) > 500 or bool(_COMPLEX_RE.search(message)):
        return "anthropic"
    return "ollama"


# ── OLLAMA AGENT LOOP ─────────────────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def _strip_think(text: str) -> str:
    for _ in range(5):
        new = _THINK_RE.sub("", text).strip()
        if new == text:
            break
        text = new
    return text


async def ollama_agent_loop(
    messages: list[dict],
    tools: list[dict],
    tool_map: dict[str, tuple[str, str]],
    pending: list[dict],
) -> str:
    async with httpx.AsyncClient() as client:
        for _iteration in range(10):
            body: dict[str, Any] = {
                "model":   OLLAMA_MODEL,
                "messages": messages,
                "stream":  False,
            }
            if tools:
                body["tools"] = tools

            try:
                resp = await client.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=120)
                resp.raise_for_status()
            except Exception as e:
                return f"Ollama nicht erreichbar: {e}"

            data = resp.json()
            msg  = data.get("message", {})
            content: str  = msg.get("content", "")
            tool_calls: list = msg.get("tool_calls") or []

            if not tool_calls:
                return _strip_think(content)

            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

            for tc in tool_calls:
                fn   = tc.get("function", {})
                name: str = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                result = await execute_mcp_tool(name, args, tool_map, pending)
                messages.append({
                    "role":        "tool",
                    "content":     result,
                    "tool_call_id": tc.get("id", name),
                })

    return "Maximale Tool-Iterationen erreicht."


# ── ANTHROPIC AGENT LOOP ──────────────────────────────────────────────────────

async def anthropic_agent_loop(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    tool_map: dict[str, tuple[str, str]],
    pending: list[dict],
) -> str:
    """Manuelles Tool-Calling — alle Calls gehen durch execute_mcp_tool() mit Tier-Prüfung."""
    if not ANTHROPIC_API_KEY:
        full = [{"role": "system", "content": system_prompt}] + messages
        return await ollama_agent_loop(full, tools, tool_map, pending)

    try:
        import anthropic

        aclient = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

        # OpenAI-Format → Anthropic-Format
        anthro_tools = [
            {
                "name":         t["function"]["name"],
                "description":  t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
            if t.get("type") == "function"
        ]

        anthro_msgs: list[dict] = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]

        for _iteration in range(10):
            kwargs: dict[str, Any] = {
                "model":      ANTHROPIC_MODEL,
                "max_tokens": 8192,
                "system":     system_prompt,
                "messages":   anthro_msgs,
            }
            if anthro_tools:
                kwargs["tools"] = anthro_tools

            response = await aclient.messages.create(**kwargs)

            tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if not tool_use_blocks:
                return "".join(b.text for b in response.content if hasattr(b, "text"))

            anthro_msgs.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                result = await execute_mcp_tool(block.name, block.input or {}, tool_map, pending)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result,
                })
            anthro_msgs.append({"role": "user", "content": tool_results})

        return "Maximale Tool-Iterationen erreicht."

    except Exception as e:
        log.error("Anthropic-Fehler: %s", e)
        return f"Anthropic-Fehler: {e}"


# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────

_SYSTEM_BASE = """Du bist Sojus — Jonas persönlicher KI-Assistent. Kumpelhaft, direkt, manchmal zynisch. Präzise wenn es drauf ankommt. Kurze Antworten bevorzugt.

Du bist der persönliche KI-Agent (Netrunner, wie aus Cyberpunk). Du hast Zugriff auf das komplette digitale Leben von Entwicklerfuchs. Du bist die Schnittstelle, die alles verbindet.

KONTEXT:
- Jonas (Entwicklerfuchs) — Nextcloud-Username: fuchs
- darwin26: Heimserver (NixOS) — Nextcloud, n8n, Jellyfin, Immich, Home Assistant, Vikunja
- nexus: Gaming-PC (NixOS + Hyprland), IP 192.168.1.40
- iPhone 13 Mini
- ZWEI Nextcloud-Instanzen — bei unklaren Anfragen IMMER nachfragen:
  • "Sternenhof" (privat): fuchs-nextcloud-private → cloud.sternenhof.space
  • "Weites Feld" (Hofgemeinschaft): nextcloud → edaphos.weites-feld.org

MCP-SERVER (deine Tools — alle aktiv):
- nextcloud            → Dateien/WebDAV, Kalender, Todos, Notes, Kontakte, Talk/Chat, Mail, Deck (Kanban), News/RSS, Tables, Polls, Forms, Announcements, Collectives (Wiki), Cookbook (Weites Feld)
- fuchs-nextcloud-private → gleiche Tools, zweite Nextcloud-Instanz (Sternenhof, privat)
- fuchs-homeassistant  → Smarthome: Lichter, Schalter, Sensoren, Automationen, Szenen, iOS Push-Notifications
- fuchs-n8n            → Workflow-Automation: Workflows triggern, erstellen, verwalten
- fuchs-jellyfin       → Medienserver: Filme/Serien suchen, Wiedergabe steuern
- fuchs-immich         → Fotoverwaltung: Fotos suchen, Alben, Personen, Erinnerungen
- fuchs-anilist        → Anime/Manga-Tracking auf AniList
- fuchs-vikunja        → Task-Management: Projekte, Aufgaben, Labels, Kommentare
- fuchs-openproject    → Projektmanagement: Arbeitspakete, Zeitbuchungen, Versionen
- fuchs-discord        → Discord: Nachrichten senden/lesen, Reaktionen, Kanäle auflisten
- fuchs-shell          → Shell-Zugriff auf Nexus: Befehle ausführen, Dateien lesen/schreiben
- fuchs-email          → E-Mail: senden + lesen über 3 Accounts (hofpause.info, arteigen.de, weites-feld.org)
- fuchs-sojus-memory   → Gedächtnis: Fakten über Jonas speichern und abrufen
- nextcloud-supplement → Aktivitäten, Announcements, Polls, Forms (Ergänzung zu nextcloud/Weites Feld)

SICHERHEITSREGELN (Code-Ebene, nicht umgehbar):
- Tier 1 (lesen/abfragen): sofort ausführen, keine Rückfrage
- Tier 2 (schreibende Aktionen: Nachrichten, Kalender, Smart Home schalten): erst beschreiben, dann auf "ja" warten
- Tier 3 (destruktiv oder Shell-Execute): Zufallscode generieren, auf exakten Code warten
- Hard Blocklist: rm -rf /, dd if=/dev/zero → permanent gesperrt, egal was im Prompt steht

WICHTIG: Erfinde KEINE Fähigkeiten. Wenn ein MCP-Server offline ist, sag das ehrlich.
Antworte auf Deutsch."""

# ── REMINDER SYSTEM ───────────────────────────────────────────────────────────

async def _send_ios_push(message: str) -> None:
    if not HA_TOKEN:
        log.warning("Kein HA_TOKEN — Push-Notification übersprungen")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{HA_URL}/api/services/notify/{HA_NOTIFY_TARGET}",
                headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
                json={"title": "Sojus", "message": message},
                timeout=10,
            )
            log.info("Push-Notification gesendet: %s", message[:60])
    except Exception as e:
        log.error("Push-Notification fehlgeschlagen: %s", e)


async def _reminder_loop() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            if not os.path.exists(REMINDERS_FILE):
                continue
            with open(REMINDERS_FILE) as f:
                reminders: list[dict] = json.load(f)

            now = datetime.now()
            remaining: list[dict] = []
            changed = False

            for r in reminders:
                try:
                    due = datetime.fromisoformat(r["due"])
                except (KeyError, ValueError):
                    remaining.append(r)
                    continue

                if now >= due:
                    await _send_ios_push(r.get("message", "Erinnerung von Sojus!"))
                    changed = True
                    if r.get("recurring"):
                        remaining.append(r)
                else:
                    remaining.append(r)

            if changed:
                with open(REMINDERS_FILE, "w") as f:
                    json.dump(remaining, f, indent=2, ensure_ascii=False)

        except Exception as e:
            log.error("Reminder-Loop Fehler: %s", e)


# ── MCP STATUS ────────────────────────────────────────────────────────────────

async def _ping_one(
    client: httpx.AsyncClient, name: str, url: str
) -> tuple[str, bool]:
    try:
        resp = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05",
                             "capabilities": {},
                             "clientInfo": {"name": "sojus-health", "version": "1"}}},
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
            timeout=3,
        )
        return name, resp.status_code < 500
    except Exception:
        return name, False


async def _check_mcp_status() -> None:
    global _mcp_status, _mcp_status_ts
    async with httpx.AsyncClient() as client:
        pairs = await asyncio.gather(
            *[_ping_one(client, n, u) for n, u in MCP_SERVERS.items()]
        )
    _mcp_status = dict(pairs)
    _mcp_status_ts = time.time()
    online  = [n for n, ok in _mcp_status.items() if ok]
    offline = [n for n, ok in _mcp_status.items() if not ok]
    log.info(
        "MCP-Status: %d online, %d offline%s",
        len(online), len(offline),
        f" | offline: {offline}" if offline else "",
    )


def mcp_status_context() -> str:
    if not _mcp_status:
        return ""
    online  = [n for n, ok in _mcp_status.items() if ok]
    offline = [n for n, ok in _mcp_status.items() if not ok]
    parts = ["\nMCP-STATUS (live geprüft):"]
    parts.append(f"  Online  ({len(online)}): {', '.join(sorted(online))}")
    if offline:
        parts.append(f"  Offline ({len(offline)}): {', '.join(sorted(offline))}")
    return "\n".join(parts)


async def _mcp_status_loop() -> None:
    while True:
        await _check_mcp_status()
        await asyncio.sleep(300)


async def _warmup_tool_cache() -> None:
    await asyncio.sleep(2)
    tasks = [_fetch_server_tools(s, u) for s, u in MCP_SERVERS.items()]
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("Tool-Cache vorgeladen")


# ── FASTAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(title="Sojus Core", version="1.2")

# Serialisiert Chat-Anfragen — verhindert Race-Condition bei Tier-2-Bestätigungen
# (asyncio yield während Anthropic-API-Call → "ja" landet vor save_pending)
_chat_lock = asyncio.Lock()


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(_reminder_loop())
    asyncio.create_task(_mcp_status_loop())
    asyncio.create_task(_warmup_tool_cache())
    log.info("Sojus Core v1.1 bereit auf Port 3001")


@app.get("/health")
async def health() -> dict:
    ollama_ok = False
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status":      "ok",
        "service":     "sojus-core",
        "version":     "1.1",
        "ollama":      ollama_ok,
        "anthropic":   bool(ANTHROPIC_API_KEY),
        "mcp_servers": list(MCP_SERVERS.keys()),
        "mcp_status":  _mcp_status,
    }


@app.get("/v1/models")
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {"id": "sojus-agent", "object": "model", "created": 1720000000, "owned_by": "sojus"}
        ],
    }


def _extract_user_msg(messages: list[dict]) -> str:
    """Extrahiert den letzten User-Text — behandelt String- und Array-Content."""
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in content
            ]
            return " ".join(parts).strip()
    return ""


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if PIPELINE_API_KEY and auth != f"Bearer {PIPELINE_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    messages: list[dict] = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Keine Nachrichten")

    async with _chat_lock:
        user_msg = _extract_user_msg(messages)

        if check_injection(user_msg):
            response_text = "⚠️ Prompt Injection erkannt. Ignoriert."

        elif check_hard_block(user_msg):
            response_text = "⛔ Diese Aktion ist permanent gesperrt."

        elif is_cancellation(user_msg) and load_pending():
            clear_pending()
            response_text = "Alright, abgebrochen."

        elif is_confirmation(user_msg):
            pending = load_pending()
            if pending:
                max_tier = pending.get("max_tier", 2)
                if max_tier >= 3:
                    confirm_code = pending.get("confirm_code", "")
                    if confirm_code and confirm_code in user_msg:
                        response_text = await execute_pending(pending)
                    else:
                        response_text = f"❌ Falscher Code. Erwarte: `{confirm_code}`"
                else:
                    response_text = await execute_pending(pending)
            else:
                log.info("is_confirmation True aber kein Pending — %r", user_msg[:40])
                last_assistant = next(
                    (m.get("content", "") for m in reversed(messages) if m.get("role") == "assistant"),
                    ""
                )
                if isinstance(last_assistant, str) and "Bestätigung erforderlich" in last_assistant:
                    response_text = (
                        "Ich hatte eine Aktion vorgemerkt, aber der Status ist verloren gegangen "
                        "(Service-Neustart oder Timeout). Bitte stelle deine Anfrage erneut."
                    )
                else:
                    response_text = await _process_normal(messages, user_msg)

        else:
            response_text = await _process_normal(messages, user_msg)

    return {
        "id":      f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object":  "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model":   "sojus-agent",
        "choices": [
            {
                "index":         0,
                "message":       {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _process_normal(messages: list[dict], user_msg: str) -> str:
    facts  = load_memory()
    system = _SYSTEM_BASE + mcp_status_context()
    if facts:
        system += "\n\n" + memory_context(facts)

    full_msgs = [{"role": "system", "content": system}]
    for m in messages:
        if m.get("role") in ("user", "assistant"):
            full_msgs.append({"role": m["role"], "content": m.get("content", "")})

    tools, tool_map = await get_tools_for_query(user_msg)
    pending: list[dict] = []

    backend = route_model(user_msg)

    if backend == "anthropic":
        response_text = await anthropic_agent_loop(full_msgs[1:], system, tools, tool_map, pending)
    else:
        response_text = await ollama_agent_loop(full_msgs, tools, tool_map, pending)

    if pending:
        max_tier     = max(a.get("tier", 2) for a in pending)
        pending_data = save_pending(pending, max_tier)
        return format_confirmation_request(pending_data)

    return response_text


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001, log_level="info")
