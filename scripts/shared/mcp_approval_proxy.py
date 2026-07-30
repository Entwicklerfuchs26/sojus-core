"""mcp-approval-proxy — protokoll-bewusster Reverse-Proxy vor der MCP-Flotte (Phase 2).

Nicht zu verwechseln mit dem PyPI-Paket `mcp-proxy` (sparfenyuk/mcp-proxy),
das auf nexus schon als stdio->HTTP-Bruecke fuer einzelne Server laeuft
(siehe fuchs-mcp-filesystem.nix, fuchs-mcp-obs.nix) — komplett andere Aufgabe.

Ein Prozess pro Host (darwin26, nexus), pro migriertem Server ein eigener
Listener auf dessen bisherigem *externen* Port. Der echte Server wandert auf
einen internen Port; der Proxy reicht alles 1:1 durch (initialize, tools/list,
SSE-GETs, ...) und liest nur POST-Bodies mit, die ein JSON-RPC `tools/call`
sind. Tier kommt aus mcp_risk_classifier (siehe docs/mcp-approval-architecture.md).
Tier 1/2 laeuft sofort durch, Tier 3 legt eine Anfrage bei mcp-approval-service
an und wartet auf Freigabe (Poll, TTL ~90s) bevor der Aufruf ans Backend
weitergereicht wird.

Fail closed: approval-service nicht erreichbar -> Tier-3-Aufruf wird abgelehnt,
niemals durchgereicht (gleiches Prinzip wie fuchs-shell in Phase 1).
"""

import asyncio
import json
import logging
import os
import time

import aiohttp
from aiohttp import web

import mcp_risk_classifier as risk

log = logging.getLogger("mcp-approval-proxy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HOST_NAME = os.environ.get("MCP_PROXY_HOST", "unknown")
CONFIG_FILE = os.environ.get("MCP_PROXY_CONFIG", "/etc/sojus/mcp-approval-proxy.json")
APPROVAL_URL = os.environ.get("APPROVAL_URL", "http://127.0.0.1:8014")
APPROVAL_TOKEN = os.environ.get("APPROVAL_API_TOKEN", "")
POLL_INTERVAL = float(os.environ.get("APPROVAL_POLL_INTERVAL", "3"))
WAIT_TIMEOUT = float(os.environ.get("APPROVAL_WAIT_TIMEOUT", "90"))

# Werden beim Durchreichen nie 1:1 kopiert — teils verbindungsspezifisch
# (aiohttp setzt sie selbst), teils würden sie mit dem gepufferten Body
# (Tier-3-Interception) nicht mehr zusammenpassen.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "host",
}


def _load_config() -> list[dict]:
    with open(CONFIG_FILE) as f:
        return json.load(f)["servers"]


def _filtered_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP}


async def _create_approval(session: aiohttp.ClientSession, server: str, tool: str, arguments: dict, tier: int) -> dict:
    async with session.post(
        f"{APPROVAL_URL}/approvals",
        json={
            "host": HOST_NAME, "server": server, "tool": tool,
            "arguments": arguments, "tier": tier, "reason": "MCP-Approval-Proxy Tier-3",
        },
        headers={"Authorization": f"Bearer {APPROVAL_TOKEN}"},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def _poll_approval(session: aiohttp.ClientSession, approval_id: str) -> dict:
    deadline = time.monotonic() + WAIT_TIMEOUT
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        async with session.get(
            f"{APPROVAL_URL}/approvals/{approval_id}",
            headers={"Authorization": f"Bearer {APPROVAL_TOKEN}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        if data["status"] != "pending":
            return data
    return {"status": "expired"}


def _jsonrpc_error(req_id, code: int, message: str) -> web.Response:
    return web.json_response(
        {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}},
        status=200,
    )


async def _relay_response(request: web.Request, resp: aiohttp.ClientResponse) -> web.StreamResponse:
    stream_resp = web.StreamResponse(status=resp.status, headers=_filtered_headers(resp.headers))
    await stream_resp.prepare(request)
    async for chunk in resp.content.iter_any():
        await stream_resp.write(chunk)
    await stream_resp.write_eof()
    return stream_resp


def make_app(server_name: str, internal_port: int) -> web.Application:
    backend_base = f"http://127.0.0.1:{internal_port}"

    async def handler(request: web.Request) -> web.StreamResponse:
        client_session: aiohttp.ClientSession = request.app["client_session"]
        target = backend_base + request.path_qs
        headers = _filtered_headers(request.headers)

        if request.method != "POST":
            async with client_session.request(request.method, target, headers=headers, data=request.content) as resp:
                return await _relay_response(request, resp)

        body = await request.read()
        tool = arguments = None
        req_id = None
        if body:
            try:
                payload = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, dict) and payload.get("method") == "tools/call":
                req_id = payload.get("id")
                params = payload.get("params", {}) or {}
                tool = params.get("name", "")
                arguments = params.get("arguments", {}) or {}

        if tool is not None:
            if risk.is_hard_blocked(json.dumps(arguments)):
                log.warning("HARD-BLOCK: %s.%s(%s)", server_name, tool, arguments)
                return _jsonrpc_error(req_id, -32000, "Blockiert: verbotenes Muster erkannt")

            tier = risk.classify_tool(tool, arguments)
            if tier == 3:
                log.warning("TIER-3 ANGEFRAGT: %s.%s(%s)", server_name, tool, arguments)
                try:
                    approval = await _create_approval(client_session, server_name, tool, arguments, tier)
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    log.error("approval-service nicht erreichbar, fail closed: %s", e)
                    return _jsonrpc_error(req_id, -32001, "Freigabe-Service nicht erreichbar — Tier-3 abgelehnt")

                decided = await _poll_approval(client_session, approval["id"])
                if decided["status"] != "approved":
                    log.warning("Tier-3 %s -> %s", approval["id"], decided["status"])
                    return _jsonrpc_error(req_id, -32002, f"Freigabe nicht erteilt: {decided['status']}")
                log.warning("Tier-3 %s freigegeben, leite weiter", approval["id"])

        async with client_session.post(target, data=body, headers=headers) as resp:
            return await _relay_response(request, resp)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)

    async def _on_startup(app):
        app["client_session"] = aiohttp.ClientSession()

    async def _on_cleanup(app):
        await app["client_session"].close()

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


async def main() -> None:
    servers = _load_config()
    if not servers:
        log.error("Keine Server in %s konfiguriert — nichts zu tun", CONFIG_FILE)
        return
    runners = []
    for s in servers:
        app = make_app(s["name"], s["internal_port"])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", s["external_port"])
        await site.start()
        runners.append(runner)
        log.info("mcp-approval-proxy: %s extern %s -> intern 127.0.0.1:%s", s["name"], s["external_port"], s["internal_port"])
    log.info("mcp-approval-proxy bereit, %d Server", len(servers))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
