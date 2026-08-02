#!/usr/bin/env python3
"""fuchs-shell — Shell MCP Server auf Nexus (Port 8012).

Gibt Sojus-Core Shell-Zugriff auf Nexus via MCP Tools.
Sicherheitsebene: Tier-Checks laufen in sojus-core vor dem Tool-Call;
dieser Server blockt nur die absolute Hard-Blacklist nochmal lokal.
"""

import os
import re
import subprocess
import asyncio
from pathlib import Path
from fastmcp import FastMCP

PORT    = int(os.environ.get("SHELL_MCP_PORT", "8012"))
API_KEY = os.environ.get("SHELL_MCP_API_KEY", "")

mcp = FastMCP(
    "fuchs-shell",
    instructions=(
        "Shell-Zugriff auf Nexus (Gaming-PC, NixOS + Hyprland). "
        "Benutzer: fuchs. Home: /home/fuchs. "
        "Tier-3-Befehle (rm -rf, nixos-rebuild, poweroff) brauchen 2× Bestätigung von Jonas — "
        "sojus-core erzwingt das bereits. Hier nur Hard-Blacklist lokal."
    ),
)

_HARD_BLOCK = re.compile(
    r"rm\s+-[rRfF]*f\s+/"
    r"|dd\s+if=/dev/(zero|random).*of=/dev/"
    r"|mkfs\."
    r"|:\(\)\{.*:\|:",
    re.IGNORECASE | re.DOTALL,
)


def _blocked(cmd: str) -> bool:
    return bool(_HARD_BLOCK.search(cmd))


@mcp.tool()
def execute_command(
    command: str,
    working_dir: str = "/home/fuchs",
    timeout: int = 30,
) -> dict:
    """Shell-Befehl auf Nexus ausführen. Gibt stdout, stderr und returncode zurück."""
    if _blocked(command):
        return {"error": "⛔ Befehl durch Hard-Blacklist blockiert.", "stdout": "", "stderr": "", "returncode": -1}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
            env={**os.environ, "HOME": "/home/fuchs", "USER": "fuchs-shell"},
        )
        return {
            "stdout":     result.stdout[:8000],
            "stderr":     result.stderr[:2000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout nach {timeout}s", "stdout": "", "stderr": "", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "stdout": "", "stderr": "", "returncode": -1}


@mcp.tool()
def read_file(path: str) -> str:
    """Datei auf Nexus lesen. Maximal 50 000 Zeichen."""
    try:
        return Path(path).read_text(errors="replace")[:50_000]
    except Exception as e:
        return f"Fehler: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Datei auf Nexus schreiben (überschreibt bestehende Datei)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Geschrieben: {path} ({len(content)} Zeichen)"
    except Exception as e:
        return f"Fehler: {e}"


@mcp.tool()
def list_directory(path: str = "/home/fuchs") -> list[str]:
    """Verzeichnis auf Nexus auflisten."""
    try:
        return sorted(str(p) for p in Path(path).iterdir())
    except Exception as e:
        return [f"Fehler: {e}"]


@mcp.tool()
def get_system_info() -> dict:
    """System-Info von Nexus: Hostname, Uptime, CPU, RAM, Disk."""
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
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
