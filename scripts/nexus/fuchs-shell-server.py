#!/usr/bin/env python3
"""fuchs-shell — Shell-MCP-Server auf Nexus (Port 8012), läuft als User 'sojus'.

Phase 1 von docs/mcp-approval-architecture.md: Tier-Klassifizierung kommt jetzt
aus der geteilten mcp_risk_classifier-Bibliothek, und Tier-3-Befehle brauchen
eine echte Freigabe über mcp-approval-service (darwin26) statt eines
selbst-ausgestellten Bestätigungs-Tokens.

Vorher lag die Absicherung in sojus-core/core.py (chat-basiertes "ja"/
Zufallscode-System, archiviert in archive/sojus-core-legacy/), danach kurz in
einem lokalen Zwei-Schritt-Token direkt in diesem Skript. Beides hatte dieselbe
Schwäche: das aufrufende Modell konnte die Bestätigung selbst zurückspielen.
mcp-approval-service behebt das — die Freigabe passiert komplett außerhalb der
Reichweite des Modells, execute_command wartet einfach synchron auf eine
Entscheidung.

Hermes hat zwar ein eigenes, ausgereifteres Approval-System (approvals.mode:
smart/manual/off), das greift aber laut Doku NUR für Hermes' natives
terminal-Tool, nicht für MCP-Server, und selbst dafür bräuchte es einen
interaktiven Kanal, den die api_server-Plattform (unser Setup) nicht hat.
Deshalb die eigene Absicherung hier (Recherche 2026-07-29).

Tier 1 (lesend)      → läuft sofort.
Tier 2 (schreibend)  → läuft sofort, wird aber laut (WARNING) geloggt.
Tier 3 (destruktiv/systemkritisch) → execute_command hält den Aufruf an und
                       wartet bis zu APPROVAL_WAIT_TIMEOUT Sekunden auf eine
                       Freigabe über mcp-approval-service (Push an Jonas via
                       Home Assistant, sofern dort konfiguriert). Ist der
                       Service nicht erreichbar oder nicht konfiguriert, wird
                       sicherheitshalber abgelehnt (fail closed).
"""

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastmcp import FastMCP

import mcp_risk_classifier as risk

log = logging.getLogger("fuchs-shell")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PORT     = int(os.environ.get("SHELL_MCP_PORT", "8012"))
HOME_DIR = os.environ.get("HOME", "/home/sojus")

# mcp-approval-service (darwin26) — Freigabe-Warteschlange für Tier-3.
APPROVAL_URL           = os.environ.get("APPROVAL_URL", "")
APPROVAL_API_TOKEN     = os.environ.get("APPROVAL_API_TOKEN", "")
APPROVAL_WAIT_TIMEOUT  = int(os.environ.get("APPROVAL_WAIT_TIMEOUT", "90"))
APPROVAL_POLL_INTERVAL = 3

# Kein eigener API-Key-Check für diesen Server selbst: wie alle anderen nexus/
# darwin26 MCP-Server verlässt sich fuchs-shell auf Netzwerk-Isolation
# (Firewall-Chain mcp-sojus-filter, nur darwin26+nexus).

mcp = FastMCP(
    "fuchs-shell",
    instructions=(
        "Shell-Zugriff auf Nexus (Gaming-PC, NixOS + Hyprland). "
        f"Läuft als unprivilegierter User 'sojus' (Home: {HOME_DIR}), NICHT als fuchs. "
        "Tier-3-Befehle (rm -rf, systemctl stop/restart, nixos-rebuild, reboot/poweroff, "
        "Befehlsverkettung) brauchen eine Freigabe durch Jonas — der Aufruf wartet "
        f"automatisch bis zu {APPROVAL_WAIT_TIMEOUT}s. Kommt keine Freigabe, einfach "
        "später erneut aufrufen."
    ),
)


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


def _await_approval(command: str) -> tuple[bool, str]:
    """Fragt mcp-approval-service um Freigabe und wartet synchron auf eine Entscheidung.

    Fail closed: ist der Service nicht konfiguriert oder nicht erreichbar,
    wird der Befehl NICHT ausgeführt.
    """
    if not (APPROVAL_URL and APPROVAL_API_TOKEN):
        return False, (
            "⛔ mcp-approval-service nicht konfiguriert (APPROVAL_URL/APPROVAL_API_TOKEN) "
            "— Tier-3 wird sicherheitshalber verweigert."
        )
    try:
        created = _approval_request("POST", "/approvals", {
            "host": "nexus",
            "server": "fuchs-shell",
            "tool": "execute_command",
            "arguments": {"command": command},
            "tier": 3,
            "reason": "Tier-3 Shell-Befehl",
        })
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.error("approval-service nicht erreichbar: %s", e)
        return False, f"⛔ mcp-approval-service nicht erreichbar — Tier-3 wird sicherheitshalber verweigert ({e})."

    approval_id = created["id"]
    log.warning("TIER-3 ANGEFRAGT, wartet auf Freigabe: %s | approval_id=%s", command, approval_id)

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

    return False, (
        f"⏳ Noch keine Entscheidung (approval_id={approval_id}). "
        "Freigabe steht noch aus — später erneut versuchen."
    )


@mcp.tool()
def execute_command(command: str, working_dir: str = HOME_DIR, timeout: int = 30) -> dict:
    """Shell-Befehl auf Nexus als User 'sojus' ausführen.

    Tier 1/2 laufen sofort. Tier 3 (destruktiv/systemkritisch) wartet auf eine
    Freigabe durch Jonas über mcp-approval-service, bevor der Befehl läuft.
    """
    if risk.is_hard_blocked(command):
        return {"error": "⛔ Befehl durch Hard-Blacklist blockiert.", "stdout": "", "stderr": "", "returncode": -1}

    tier = risk.classify_shell_command(command)

    if tier >= 3:
        ok, msg = _await_approval(command)
        if not ok:
            return {"error": msg, "tier": tier, "stdout": "", "stderr": "", "returncode": -1}
        log.warning("TIER-3 freigegeben, wird ausgeführt: %s", command)
    elif tier == 2:
        log.warning("TIER-2 Befehl: %s", command)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
            env={**os.environ, "HOME": HOME_DIR},
        )
        return {
            "stdout":     result.stdout[:8000],
            "stderr":     result.stderr[:2000],
            "returncode": result.returncode,
            "tier":       tier,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout nach {timeout}s", "stdout": "", "stderr": "", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "stdout": "", "stderr": "", "returncode": -1}


@mcp.tool()
def read_file(path: str) -> str:
    """Datei auf Nexus lesen (als sojus). Maximal 50 000 Zeichen."""
    try:
        return Path(path).read_text(errors="replace")[:50_000]
    except Exception as e:
        return f"Fehler: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Datei auf Nexus schreiben (als sojus, überschreibt bestehende Datei)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Geschrieben: {path} ({len(content)} Zeichen)"
    except Exception as e:
        return f"Fehler: {e}"


@mcp.tool()
def list_directory(path: str = HOME_DIR) -> list[str]:
    """Verzeichnis auf Nexus auflisten (als sojus)."""
    try:
        return sorted(str(p) for p in Path(path).iterdir())
    except Exception as e:
        return [f"Fehler: {e}"]


@mcp.tool()
def get_system_info() -> dict:
    """System-Info von Nexus: Hostname, Uptime, CPU, RAM, Disk, GPU."""
    info: dict = {}
    for key, cmd in [
        ("hostname",  "hostname"),
        ("uptime",    "uptime -p"),
        ("cpu_usage", "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4\"%\"}'"),
        ("ram",       "free -h | awk '/^Mem/{print $3\"/\"$2}'"),
        ("disk_home", "df -h /home | awk 'NR==2{print $3\"/\"$2\" (\"$5\" belegt)\"}'"),
        ("gpu",       "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo 'keine NVIDIA-GPU'"),
    ]:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        info[key] = r.stdout.strip() or r.stderr.strip()
    return info


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="192.168.1.40", port=PORT)
