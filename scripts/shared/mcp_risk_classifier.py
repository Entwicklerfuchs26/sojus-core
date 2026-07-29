"""mcp_risk_classifier — geteilte Tier-Klassifizierung für MCP-Tool-Aufrufe.

Format von tool_tiers.json (config/tool_tiers.json) 1:1 aus
archive/sojus-core-legacy/ übernommen und für mehrere Server nutzbar gemacht.

Tier 1 = lesend, Tier 2 = schreibend, Tier 3 = destruktiv/systemkritisch.
"content_based"-Overrides (z.B. execute_command) klassifizieren nach dem
tatsächlichen Befehlsinhalt statt nach Tool-Namen — siehe classify_shell_command().

Phase 1 (docs/mcp-approval-architecture.md): nur Regex, kein "smart mode"
(kein LLM-Call für Grenzfälle — bewusste Entscheidung, siehe Doku).
"""

import json
import os
import re

TOOL_TIERS_FILE = os.environ.get("TOOL_TIERS_FILE", "/etc/sojus/tool_tiers.json")

_TIER3_VERBS = frozenset({
    "delete", "remove", "purge", "destroy", "trash", "wipe", "erase", "drop",
})
_TIER2_VERBS = frozenset({
    "create", "update", "write", "send", "post", "set", "add", "insert",
    "edit", "modify", "upload", "toggle", "activate", "enable", "disable",
    "trigger", "fire", "turn", "start", "stop", "pause", "play",
    "restart", "reload", "run", "execute", "dispatch", "save", "append",
    "import", "export", "encode", "render", "move", "copy", "archive",
    "restore", "unarchive", "reorder", "assign", "unassign", "attach",
    "detach", "follow", "mark", "vote", "favorite", "favourite",
    "click", "navigate", "close", "evaluate", "new", "focus", "notify",
    "deactivate", "bulk", "reindex", "manage", "complete", "announce",
    "invite", "batch", "open", "like",
})

# ── Hard-Blacklist — greift immer, unabhängig von Tier ────────────────────
# Basis aus archive/sojus-core-legacy/core.py, erweitert um Muster aus Hermes'
# eigener (dokumentierter) Approval-Blockliste — die gilt aber nur für Hermes'
# natives terminal-Tool, nicht für MCP-Server. Deshalb hier übernommen.
HARD_BLOCK_RE = re.compile(
    r"rm\s+-[rRfF]*f\s+/"
    r"|dd\s+if=/dev/(zero|random).*of=/dev/"
    r"|mkfs\."
    r"|:\(\)\{.*:\|:"
    r"|kill\s+-9\s+-1\b"
    r"|\|\s*(sh|bash|zsh)\b"
    r"|bash\s*<\(\s*curl"
    r"|wget\s+-O-.*\|\s*(sh|bash)",
    re.IGNORECASE | re.DOTALL,
)


def is_hard_blocked(text: str) -> bool:
    return bool(HARD_BLOCK_RE.search(text or ""))


# ── Shell-Befehl-Klassifizierung (für "content_based"-Overrides) ──────────
_EXEC_TIER3_RE = re.compile(
    r"\bpoweroff\b|\bshutdown\b|\breboot\b"
    r"|\bnixos-rebuild\b"
    r"|\bsystemctl\s+(stop|restart|disable|mask)\b"
    r"|\brm\s+-[rRfF]*[fF]\b"
    r"|\bmkfs\b|\bdd\s+if="
    r"|\bDROP\s+TABLE\b|\bTRUNCATE\s+TABLE\b|\bDELETE\s+FROM\b"
    r"|\bchmod\s+-R\s+(000|777)\b|\bchown\s+-R\s+root\b"
    r"|>\s*/etc/\S"
    r"|\bpkill\s+-9\b|\bkill\s+-9\b"
    r"|\bdocker\s+(stop|kill|restart)\b"
    r"|>\s*/dev/sd",
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


def classify_shell_command(cmd: str) -> int:
    cmd = (cmd or "").strip()
    if not cmd:
        return 2
    if _EXEC_TIER3_RE.search(cmd) or _CHAIN_RE.search(cmd):
        return 3
    first = cmd.split()[0] if cmd.split() else ""
    if first in _READONLY_CMDS:
        return 1
    return 2


# ── Tool-Namen-Klassifizierung (Overrides + Verb-Auto-Engine) ─────────────
_tiers_cache: dict | None = None


def _load_tiers() -> dict:
    global _tiers_cache
    if _tiers_cache is None:
        try:
            with open(TOOL_TIERS_FILE) as f:
                _tiers_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _tiers_cache = {}
    return _tiers_cache


def _auto_classify(tool_name: str) -> int:
    tokens = set(tool_name.lower().split("_"))
    if tokens & _TIER3_VERBS:
        return 3
    if tokens & _TIER2_VERBS:
        return 2
    return 1


def classify_tool(tool_name: str, arguments: dict | None = None) -> int:
    """Tier für einen MCP-Tool-Aufruf: 1=lesend, 2=schreibend, 3=destruktiv.

    arguments wird nur für "content_based"-Overrides gebraucht (execute_command
    o.ä.) — dort zählt der tatsächliche Befehlsinhalt, nicht der Tool-Name.
    """
    arguments = arguments or {}
    tiers = _load_tiers()
    overrides: dict = tiers.get("overrides", {})
    name = tool_name.lower()

    if name in overrides:
        val = overrides[name]
        if val == "content_based":
            cmd = str(arguments.get("command", arguments.get("cmd", "")))
            return classify_shell_command(cmd)
        return int(val)

    return _auto_classify(name)
