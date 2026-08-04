#!/usr/bin/env python3
# Sojus Chat Backend — Context-Store (SQLite) + REST API + WebSocket.
# Läuft als eigenständiger ASGI-Prozess (kein "uvicorn <module>" nötig,
# main() startet uvicorn direkt), Konfiguration ausschließlich über
# Umgebungsvariablen (siehe darwin26/sojus-api.nix).

import asyncio
import json
import logging
import os
import sqlite3
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

logger = logging.getLogger("sojus-api")

DB_DIR = Path(os.environ.get("SOJUS_API_DB_DIR", "/var/lib/sojus-api"))
ATTACHMENTS_DIR = Path(os.environ.get("SOJUS_API_ATTACHMENTS_DIR", "/var/lib/sojus-api/attachments"))
DB_PATH = DB_DIR / "context.db"

# Hermes (Nous Research Agent, OpenAI-kompatible API) — generiert die
# Assistant-Antworten. Läuft als eigener Service auf demselben Host
# (siehe darwin26/hermes.nix), daher per Default über localhost erreichbar.
HERMES_URL = os.environ.get("HERMES_URL", "http://127.0.0.1:3002/v1/chat/completions")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
HERMES_MODEL = os.environ.get("HERMES_MODEL", "claude-haiku-4-5-20251001")
HERMES_CONTEXT_SIZE = int(os.environ.get("HERMES_CONTEXT_SIZE", "20"))
# Hermes durchläuft pro Anfrage Tool-Registry-Checks + Modellaufruf — das
# dauert erfahrungsgemäß mehrere zehn Sekunden, daher großzügiger Timeout.
HERMES_TIMEOUT = float(os.environ.get("HERMES_TIMEOUT", "180"))

DB_DIR.mkdir(parents=True, exist_ok=True)
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            channel TEXT NOT NULL,
            type TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            metadata TEXT,
            session_id TEXT
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            filename TEXT,
            mimetype TEXT,
            size INTEGER,
            path TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


init_db()

app = FastAPI(title="Sojus Chat API")


def row_to_message(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (TypeError, json.JSONDecodeError):
            pass
    return d


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


class MessageIn(BaseModel):
    channel: str = "text"
    type: str = "text"
    role: str
    content: Optional[str] = None
    metadata: Optional[dict] = None
    session_id: Optional[str] = None


class TTSIn(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


def insert_message_row(msg: MessageIn) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    metadata_json = json.dumps(msg.metadata) if msg.metadata is not None else None
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO messages (timestamp, channel, type, role, content, metadata, session_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (timestamp, msg.channel, msg.type, msg.role, msg.content, metadata_json, msg.session_id),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return row_to_message(row)


@app.post("/messages")
async def create_message(msg: MessageIn):
    message = insert_message_row(msg)
    await manager.broadcast({"type": "new_message", "message": message})
    if msg.role == "user":
        asyncio.create_task(generate_hermes_reply())
    return message


async def generate_hermes_reply() -> None:
    # Läuft losgelöst vom auslösenden Request (create_task) — der Client
    # bekommt sein POST /messages sofort bestätigt, die Antwort kommt
    # Sekunden später separat per WebSocket-Broadcast rein.
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (HERMES_CONTEXT_SIZE,)
    ).fetchall()
    conn.close()
    context = [row_to_message(r) for r in reversed(rows)]
    hermes_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in context
        if m["role"] in ("user", "assistant") and m["content"]
    ]
    if not hermes_messages:
        return

    try:
        async with httpx.AsyncClient(timeout=HERMES_TIMEOUT) as client:
            resp = await client.post(
                HERMES_URL,
                headers={"Authorization": f"Bearer {HERMES_API_KEY}"},
                json={"model": HERMES_MODEL, "messages": hermes_messages},
            )
            resp.raise_for_status()
            data = resp.json()
        reply_text = data["choices"][0]["message"]["content"]
    except Exception:
        logger.exception("Hermes-Anfrage fehlgeschlagen")
        reply_text = "⚠️ Hermes antwortet gerade nicht (Fehler bei der Anfrage)."

    reply_message = insert_message_row(MessageIn(role="assistant", content=reply_text))
    await manager.broadcast({"type": "new_message", "message": reply_message})


@app.get("/messages")
def list_messages(limit: int = 50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [row_to_message(r) for r in rows]


@app.get("/messages/context")
def context_messages(n: int = 20):
    # Chronologisch aufsteigend zurückgeben — direkt als Konversationsverlauf
    # für Kontext-Injection verwendbar, ohne dass der Aufrufer selbst dreht.
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    return [row_to_message(r) for r in reversed(rows)]


@app.delete("/messages/{message_id}")
async def delete_message(message_id: int):
    conn = get_db()
    row = conn.execute("SELECT id FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Nachricht nicht gefunden")
    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    await manager.broadcast({"type": "message_deleted", "id": message_id})
    return {"status": "deleted", "id": message_id}


@app.post("/attachments")
async def upload_attachment(file: UploadFile = File(...)):
    attachment_id = str(uuid.uuid4())
    suffix = Path(file.filename or "").suffix
    stored_path = ATTACHMENTS_DIR / f"{attachment_id}{suffix}"

    data = await file.read()
    stored_path.write_bytes(data)

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO attachments (id, filename, mimetype, size, path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (attachment_id, file.filename, file.content_type, len(data), str(stored_path), created_at),
    )
    conn.commit()
    conn.close()

    return {"id": attachment_id, "url": f"/attachments/{attachment_id}"}


@app.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    path = Path(row["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei fehlt auf der Platte")
    return FileResponse(path, media_type=row["mimetype"] or "application/octet-stream", filename=row["filename"] or path.name)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Clients senden aktuell nichts Sinnvolles — der Empfangs-Loop
            # hält die Verbindung offen und erkennt Disconnects zuverlässig.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Voice-Stubs ──────────────────────────────────────────────────────────
# Endpunkte existieren und antworten korrekt, aber (noch) ohne echte Logik.

@app.post("/voice/stt")
async def voice_stt(request: Request):
    # TODO: Whisper STT hier einhängen
    await request.body()
    return {"text": "[STT nicht aktiv]"}


def _empty_wav() -> bytes:
    channels, sample_rate, bits_per_sample = 1, 16000, 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    header = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample)
    header += b"data" + struct.pack("<I", 0)
    return header


@app.post("/voice/tts")
async def voice_tts(payload: TTSIn):
    # TODO: Chatterbox TTS hier einhängen
    return Response(content=_empty_wav(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SOJUS_API_PORT", "7430")))
