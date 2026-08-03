#!/usr/bin/env python3
"""fuchs-sandbox-control — schmaler MCP-Server auf darwin26 (Port 8015).

Gibt Hermes genau drei Fähigkeiten, um den sandbox-sojus-Container (siehe
darwin26/containers.nix) selbst zu steuern, während er dort Sojus-Core-
Änderungen testet — nichts weiter. Kein allgemeines execute_command wie
fuchs-shell auf Nexus: Start/Stop/Status sind Tier 2 (laufen sofort, laut
geloggt), Sync (Kopie zurück ins Original) ist Tier 3 und wartet auf eine
echte Freigabe über mcp-approval-service (HA-Push an Jonas), bevor irgendwas
geschrieben wird — mirrored von fuchs-shell-server.py's _await_approval.

Läuft als eigener unprivilegierter Service-User (sandbox-sojus-ctl), NICHT
als fuchs oder hermes. Die zugrunde liegenden Befehle (systemctl start/stop/
status container-sandbox-sojus, das feste sync-Skript) sind über eine exakte
NOPASSWD-sudoers-Regel freigegeben, siehe darwin26/sandbox-sojus-control.nix.
"""

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request

from fastmcp import FastMCP

log = logging.getLogger("fuchs-sandbox-control")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PORT = int(os.environ.get("SANDBOX_CONTROL_PORT", "8015"))

SYNC_SCRIPT = os.environ.get("SYNC_SCRIPT", "/var/lib/sandbox-sojus-ctl/bin/sandbox-sojus-sync.sh")
CONTAINER = "container@sandbox-sojus.service"

# mcp-approval-service läuft lokal auf darwin26 (gleicher Host).
APPROVAL_URL = os.environ.get("APPROVAL_URL", "http://127.0.0.1:8014")
APPROVAL_API_TOKEN = os.environ.get("APPROVAL_API_TOKEN", "")
APPROVAL_WAIT_TIMEOUT = int(os.environ.get("APPROVAL_WAIT_TIMEOUT", "90"))
APPROVAL_POLL_INTERVAL = 3

mcp = FastMCP(
    "fuchs-sandbox-control",
    instructions=(
        "Steuerung für den sandbox-sojus-Testcontainer auf darwin26. "
        "sandbox_sojus_start/stop/status laufen sofort. sandbox_sojus_sync "
        "(Kopie vom Container zurück in /home/fuchs/sojus-core) braucht eine "
        f"Freigabe durch Jonas — wartet automatisch bis zu {APPROVAL_WAIT_TIMEOUT}s. "
        "Erst NACH einem erfolgreichen Sync entscheidet Jonas separat per "
        "nixos-rebuild switch, ob die Änderung live geht."
    ),
)


def _run_sudo(args: list[str], timeout: int = 60) -> dict:
    try:
        result = subprocess.run(
            ["sudo", "-n", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout nach {timeout}s", "stdout": "", "stderr": "", "returncode": -1}


def _approval_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{APPROVAL_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {APPROVAL_API_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _await_sync_approval(reason: str) -> tuple[bool, str]:
    """Fail closed: ohne erreichbaren/konfigurierten approval-service kein Sync."""
    if not APPROVAL_API_TOKEN:
        return False, "⛔ APPROVAL_API_TOKEN nicht konfiguriert — Sync wird sicherheitshalber verweigert."
    try:
        created = _approval_request("POST", "/approvals", {
            "host": "darwin26",
            "server": "fuchs-sandbox-control",
            "tool": "sandbox_sojus_sync",
            "arguments": {"reason": reason},
            "tier": 3,
            "reason": reason,
        })
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.error("approval-service nicht erreichbar: %s", e)
        return False, f"⛔ mcp-approval-service nicht erreichbar — Sync wird verweigert ({e})."

    approval_id = created["id"]
    log.warning("SYNC ANGEFRAGT, wartet auf Freigabe: approval_id=%s reason=%s", approval_id, reason)

    deadline = time.time() + APPROVAL_WAIT_TIMEOUT
    while time.time() < deadline:
        time.sleep(APPROVAL_POLL_INTERVAL)
        try:
            status = _approval_request("GET", f"/approvals/{approval_id}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            log.error("approval-service Poll fehlgeschlagen: %s", e)
            continue

        if status["status"] == "approved":
            return True, ""
        if status["status"] == "rejected":
            return False, f"❌ Abgelehnt: {status.get('decision_note') or 'kein Grund angegeben'}"
        if status["status"] == "expired":
            return False, "⏱️ Freigabe-Zeitfenster abgelaufen, ohne Entscheidung."

    return False, f"⏳ Noch keine Entscheidung (approval_id={approval_id}). Später erneut versuchen."


@mcp.tool()
def sandbox_sojus_start() -> dict:
    """sandbox-sojus-Container starten (Tier 2, läuft sofort)."""
    log.warning("TIER-2: sandbox_sojus_start")
    return _run_sudo(["systemctl", "start", CONTAINER])


@mcp.tool()
def sandbox_sojus_stop() -> dict:
    """sandbox-sojus-Container stoppen (Tier 2, läuft sofort)."""
    log.warning("TIER-2: sandbox_sojus_stop")
    return _run_sudo(["systemctl", "stop", CONTAINER])


@mcp.tool()
def sandbox_sojus_status() -> dict:
    """Status des sandbox-sojus-Containers abfragen (Tier 1, lesend)."""
    return _run_sudo(["systemctl", "status", CONTAINER, "--no-pager"])


@mcp.tool()
def sandbox_sojus_sync(reason: str) -> dict:
    """Getestete Änderungen vom Container zurück nach /home/fuchs/sojus-core kopieren.

    Tier 3 — wartet zuerst auf eine Freigabe durch Jonas (HA-Push über
    mcp-approval-service), bevor irgendetwas geschrieben wird.
    """
    ok, msg = _await_sync_approval(reason)
    if not ok:
        return {"error": msg, "stdout": "", "stderr": "", "returncode": -1}
    log.warning("SYNC freigegeben, wird ausgeführt: reason=%s", reason)
    return _run_sudo([SYNC_SCRIPT])


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=PORT)
