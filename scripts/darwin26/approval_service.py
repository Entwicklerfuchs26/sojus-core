"""mcp-approval-service — zentrale Freigabe-Warteschlange für Tier-3 MCP-Tool-Aufrufe.

Läuft auf darwin26 (Port siehe darwin26/mcp-approval-service.nix). Nimmt
Genehmigungsanfragen von MCP-Servern entgegen (z.B. fuchs-shell auf nexus),
hält den Zustand in SQLite, benachrichtigt optional über Home Assistant, und
beantwortet Freigaben/Ablehnungen über eine kleine REST-API.

Auth: geteilter Bearer-Token (APPROVAL_API_TOKEN) + Firewall — MVP-Niveau,
Entscheidung siehe docs/mcp-approval-architecture.md ("Offene Entscheidungen" #1).
Notifier: pluggable, aktuell nur Home Assistant (optional, HA_URL/HA_TOKEN).
Die künftige Sojus-GUI braucht kein Plugin — sie liest/schreibt direkt gegen
diese API (siehe /approvals/stream für einen Live-Feed).

Kein "smart mode": Klassifizierung passiert beim Aufrufer (mcp_risk_classifier),
dieser Service kennt nur noch Tier-Zahl + Grund, keine eigene Risikoeinschätzung
(Entscheidung siehe docs/mcp-approval-architecture.md, Frage #2).
"""

import asyncio
import json
import logging
import os
import secrets as secrets_mod
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

log = logging.getLogger("mcp-approval-service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DB_PATH = os.environ.get("APPROVAL_DB_PATH", "/var/lib/mcp-approval/approvals.db")
TOKEN = os.environ.get("APPROVAL_API_TOKEN", "")
TTL_SECONDS = int(os.environ.get("APPROVAL_TTL_SECONDS", "300"))

HA_URL = os.environ.get("HA_URL", "")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_NOTIFY_SERVICE = os.environ.get("HA_NOTIFY_SERVICE", "notify/mobile_app_iphone")

app = FastAPI(title="mcp-approval-service")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with closing(_db()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id            TEXT PRIMARY KEY,
                created_at    REAL NOT NULL,
                host          TEXT NOT NULL,
                server        TEXT NOT NULL,
                tool          TEXT NOT NULL,
                arguments     TEXT NOT NULL,
                tier          INTEGER NOT NULL,
                reason        TEXT,
                status        TEXT NOT NULL DEFAULT 'pending',
                decided_at    REAL,
                decision_note TEXT
            )
        """)


_init_db()


def _require_token(authorization: str | None) -> None:
    if not TOKEN:
        raise HTTPException(500, "APPROVAL_API_TOKEN nicht konfiguriert — Service verweigert Betrieb")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Ungültiges oder fehlendes Bearer-Token")


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["arguments"] = json.loads(d["arguments"])
    return d


def _expire_if_due(d: dict) -> dict:
    if d["status"] == "pending" and time.time() - d["created_at"] > TTL_SECONDS:
        with closing(_db()) as conn, conn:
            conn.execute(
                "UPDATE approvals SET status='expired', decided_at=? WHERE id=? AND status='pending'",
                (time.time(), d["id"]),
            )
        d["status"] = "expired"
        d["decided_at"] = time.time()
    return d


def _notify(approval: dict) -> None:
    log.warning(
        "TIER-%s ANGEFRAGT: %s.%s(%s) — id=%s host=%s",
        approval["tier"], approval["server"], approval["tool"],
        approval["arguments"], approval["id"], approval["host"],
    )
    if not (HA_URL and HA_TOKEN):
        return
    try:
        req = urllib.request.Request(
            f"{HA_URL.rstrip('/')}/api/services/{HA_NOTIFY_SERVICE}",
            data=json.dumps({
                "title": f"⚠️ Sojus: Freigabe nötig (Tier {approval['tier']})",
                "message": f"{approval['server']}.{approval['tool']}({approval['arguments']})\nID: {approval['id']}",
            }).encode(),
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except (urllib.error.URLError, OSError) as e:
        log.error("HA-Notify fehlgeschlagen: %s", e)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/approvals")
def create_approval(body: dict, authorization: str | None = Header(None)) -> dict:
    _require_token(authorization)
    for field in ("host", "server", "tool", "arguments", "tier"):
        if field not in body:
            raise HTTPException(400, f"Feld fehlt: {field}")

    approval_id = secrets_mod.token_hex(8)
    row = {
        "id": approval_id,
        "created_at": time.time(),
        "host": str(body["host"]),
        "server": str(body["server"]),
        "tool": str(body["tool"]),
        "arguments": json.dumps(body["arguments"]),
        "tier": int(body["tier"]),
        "reason": str(body.get("reason", "")),
        "status": "pending",
    }
    with closing(_db()) as conn, conn:
        conn.execute(
            "INSERT INTO approvals (id, created_at, host, server, tool, arguments, tier, reason, status) "
            "VALUES (:id, :created_at, :host, :server, :tool, :arguments, :tier, :reason, :status)",
            row,
        )
    result = _row_to_dict(row | {"decided_at": None, "decision_note": None})
    _notify(result)
    return result


@app.get("/approvals")
def list_approvals(status: str | None = None, authorization: str | None = Header(None)) -> list[dict]:
    _require_token(authorization)
    with closing(_db()) as conn:
        rows = conn.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT 100").fetchall()
    results = [_expire_if_due(_row_to_dict(r)) for r in rows]
    if status:
        results = [r for r in results if r["status"] == status]
    return results


@app.get("/approvals/{approval_id}")
def get_approval(approval_id: str, authorization: str | None = Header(None)) -> dict:
    _require_token(authorization)
    with closing(_db()) as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unbekannte Approval-ID")
    return _expire_if_due(_row_to_dict(row))


def _decide(approval_id: str, new_status: str, note: str) -> dict:
    with closing(_db()) as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unbekannte Approval-ID")
    current = _expire_if_due(_row_to_dict(row))
    if current["status"] != "pending":
        raise HTTPException(409, f"Bereits entschieden/abgelaufen: {current['status']}")

    with closing(_db()) as conn, conn:
        conn.execute(
            "UPDATE approvals SET status=?, decided_at=?, decision_note=? WHERE id=?",
            (new_status, time.time(), note, approval_id),
        )
    log.warning("Approval %s -> %s (%s)", approval_id, new_status, note)
    current["status"] = new_status
    current["decided_at"] = time.time()
    current["decision_note"] = note
    return current


@app.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, body: dict | None = None, authorization: str | None = Header(None)) -> dict:
    _require_token(authorization)
    return _decide(approval_id, "approved", (body or {}).get("comment", ""))


@app.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, body: dict | None = None, authorization: str | None = Header(None)) -> dict:
    _require_token(authorization)
    return _decide(approval_id, "rejected", (body or {}).get("reason", ""))


@app.get("/approvals/stream")
async def stream(authorization: str | None = Header(None)) -> StreamingResponse:
    _require_token(authorization)

    async def gen():
        last_seen = 0.0
        while True:
            with closing(_db()) as conn:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE created_at > ? ORDER BY created_at ASC", (last_seen,)
                ).fetchall()
            for r in rows:
                d = _expire_if_due(_row_to_dict(r))
                last_seen = max(last_seen, d["created_at"])
                yield f"data: {json.dumps(d)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")
