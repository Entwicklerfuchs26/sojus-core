#!/usr/bin/env python3
"""fuchs-shell — Shell-MCP-Server auf Nexus (Port 8012), läuft als User 'sojus'.

Vorher lag die Tier-Klassifizierung + Bestätigungspflicht für gefährliche Befehle
in sojus-core/core.py (chat-basiertes "ja"/Zufallscode-System). core.py wurde mit
der Hermes-Migration archiviert (archive/sojus-core-legacy/) — die Absicherung
ist deshalb hier selbst eingebaut (Tier-Logik 1:1 aus core.py übernommen), damit
Hermes nicht ungeschützt auf Nexus shellen kann.

Tier 1 (lesend)      → läuft sofort.
Tier 2 (schreibend)  → läuft sofort, wird aber laut (WARNING) geloggt.
Tier 3 (destruktiv/systemkritisch: rm -rf, systemctl stop/restart/disable/mask,
        nixos-rebuild, reboot/poweroff/shutdown, Befehlsverkettung &&/||/;)
                     → erster Aufruf ohne confirm_token wird abgelehnt und liefert
                       einen einmaligen Token zurück (2 Min gültig, nur für exakt
                       diesen Befehl). Zweiter Aufruf MIT confirm_token führt aus.
                       Optional: Push über Home Assistant, falls HA_URL/HA_TOKEN
                       gesetzt sind (sonst nur Log — siehe README-Hinweis unten).

Das ist kein hartes Human-in-the-loop-Gate (ein Modell könnte den Token im
selben Turn zurückspielen) — aber Friktion + Audit-Log + optionaler Push sind
strikt mehr als vorher (nur 4 Hard-Blacklist-Regexe, kein Tier-Konzept mehr).
"""

import hashlib
import json
import logging
import os
import re
import secrets as secrets_mod
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastmcp import FastMCP

log = logging.getLogger("fuchs-shell")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PORT     = int(os.environ.get("SHELL_MCP_PORT", "8012"))
HOME_DIR = os.environ.get("HOME", "/home/sojus")

# Kein eigener API-Key-Check: wie alle anderen nexus/darwin26 MCP-Server verlässt
# sich fuchs-shell auf Netzwerk-Isolation (Firewall-Chain mcp-sojus-filter, nur
# darwin26+nexus) statt auf Transport-Auth — fastmcps streamable-http nimmt hier
# keinen einfachen Bearer-Token entgegen. Systemweite Auth wäre ein separates Thema.

# Optional — Push-Benachrichtigung bei Tier-3-Anfragen. Leer = nur Log.
HA_URL            = os.environ.get("HA_URL", "")
HA_TOKEN          = os.environ.get("HA_TOKEN", "")
HA_NOTIFY_SERVICE = os.environ.get("HA_NOTIFY_SERVICE", "notify/mobile_app_iphone")

mcp = FastMCP(
    "fuchs-shell",
    instructions=(
        "Shell-Zugriff auf Nexus (Gaming-PC, NixOS + Hyprland). "
        f"Läuft als unprivilegierter User 'sojus' (Home: {HOME_DIR}), NICHT als fuchs. "
        "Tier-3-Befehle (rm -rf, systemctl stop/restart, nixos-rebuild, reboot/poweroff, "
        "Befehlsverkettung) brauchen zwei execute_command-Aufrufe: erst ohne confirm_token "
        "(liefert Token zurück), dann mit confirm_token exakt aus Antwort 1."
    ),
)

# ── Hard-Blacklist — greift immer, unabhängig von Tier/Token ─────────────────
_HARD_BLOCK_RE = re.compile(
    r"rm\s+-[rRfF]*f\s+/"
    r"|dd\s+if=/dev/(zero|random).*of=/dev/"
    r"|mkfs\."
    r"|:\(\)\{.*:\|:",
    re.IGNORECASE | re.DOTALL,
)


def _hard_blocked(cmd: str) -> bool:
    return bool(_HARD_BLOCK_RE.search(cmd))


# ── Tier-Klassifizierung — 1:1 aus archive/sojus-core-legacy/core.py portiert ─
_TIER3_CMD_RE = re.compile(
    r"\bpoweroff\b|\bshutdown\b|\breboot\b"
    r"|\bnixos-rebuild\b"
    r"|\bsystemctl\s+(stop|restart|disable|mask)\b"
    r"|\brm\s+-[rRfF]*[fF]\b"
    r"|\bmkfs\b|\bdd\s+if=",
    re.IGNORECASE,
)
_CHAIN_RE = re.compile(r"&&|\|\||;")
_READONLY_CMDS = frozenset({
    "ls", "ll", "la", "cat", "head", "tail", "grep", "find", "locate",
    "df", "du", "free", "ps", "uptime", "who", "whoami", "pwd", "echo",
    "env", "printenv", "date", "cal", "id", "groups", "uname", "hostname",
    "journalctl", "dmesg", "lsblk", "lsusb", "lspci", "lscpu",
    "ip", "nmcli", "netstat", "ss", "systemctl",
})


def _classify_tier(cmd: str) -> int:
    cmd = cmd.strip()
    if not cmd:
        return 2
    if _TIER3_CMD_RE.search(cmd) or _CHAIN_RE.search(cmd):
        return 3
    first = cmd.split()[0] if cmd.split() else ""
    if first in _READONLY_CMDS:
        return 1
    return 2


# ── Tier-3 Bestätigungs-Tokens (in-memory, pro Prozess) ──────────────────────
_TOKEN_TTL = 120  # Sekunden
_pending_tier3: dict[str, tuple[str, float]] = {}


def _cmd_hash(cmd: str) -> str:
    return hashlib.sha256(cmd.encode()).hexdigest()[:16]


def _notify_tier3_pending(cmd: str, token: str) -> None:
    log.warning("TIER-3 ANGEFRAGT (wartet auf Bestätigung): %s | Token: %s", cmd, token)
    if not (HA_URL and HA_TOKEN):
        return
    try:
        req = urllib.request.Request(
            f"{HA_URL.rstrip('/')}/api/services/{HA_NOTIFY_SERVICE}",
            data=json.dumps({
                "title": "⚠️ Sojus: Tier-3 Shell-Befehl angefragt (Nexus)",
                "message": f"{cmd}\nToken: {token} (2 Min gültig)",
            }).encode(),
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except (urllib.error.URLError, OSError) as e:
        log.error("HA-Notify fehlgeschlagen: %s", e)


def _check_or_issue_token(cmd: str, provided: str) -> tuple[bool, str]:
    h = _cmd_hash(cmd)
    now = time.time()
    for k in [k for k, (_, exp) in _pending_tier3.items() if exp < now]:
        del _pending_tier3[k]

    if provided:
        entry = _pending_tier3.get(h)
        if entry and entry[0] == provided:
            del _pending_tier3[h]
            return True, ""
        return False, "❌ Ungültiger oder abgelaufener Bestätigungs-Token für genau diesen Befehl."

    token = secrets_mod.token_hex(4)
    _pending_tier3[h] = (token, now + _TOKEN_TTL)
    _notify_tier3_pending(cmd, token)
    return False, (
        f"🔴 Tier-3 (destruktiv/systemkritisch): `{cmd}`\n"
        f"Erneut aufrufen mit confirm_token=\"{token}\" um auszuführen (2 Minuten gültig, "
        "nur für exakt diesen Befehl)."
    )


@mcp.tool()
def execute_command(
    command: str,
    working_dir: str = HOME_DIR,
    timeout: int = 30,
    confirm_token: str = "",
) -> dict:
    """Shell-Befehl auf Nexus als User 'sojus' ausführen.

    Tier 1/2 laufen sofort. Tier 3 (destruktiv/systemkritisch) braucht zwei
    Aufrufe: ohne confirm_token → Token wird zurückgegeben; mit confirm_token
    aus der ersten Antwort → wird ausgeführt.
    """
    if _hard_blocked(command):
        return {"error": "⛔ Befehl durch Hard-Blacklist blockiert.", "stdout": "", "stderr": "", "returncode": -1}

    tier = _classify_tier(command)

    if tier >= 3:
        ok, msg = _check_or_issue_token(command, confirm_token)
        if not ok:
            return {"error": msg, "tier": tier, "stdout": "", "stderr": "", "returncode": -1}
        log.warning("TIER-3 bestätigt, wird ausgeführt: %s", command)
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
