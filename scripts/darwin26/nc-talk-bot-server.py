#!/usr/bin/env python3
# NC Talk Bot — Webhook-Empfänger für Nextcloud Talk auf edaphos.weites-feld.org,
# leitet erlaubte Nachrichten an die kaira-Agent-Instanz weiter und postet die
# Antwort als Bot in den jeweiligen Talk-Chat zurück.
#
# API-Referenz (offizielle Nextcloud-Talk-Doku, https://nextcloud-talk.readthedocs.io/en/latest/bots/):
#   - Eingehende Signatur: HMAC-SHA256(secret, X-Nextcloud-Talk-Random + raw_body),
#     Header X-Nextcloud-Talk-Signature (hex, case-insensitive Vergleich).
#   - Antwort als Bot: POST /ocs/v2.php/apps/spreed/api/v1/bot/{token}/message,
#     Signatur HMAC-SHA256(secret, X-Nextcloud-Talk-Bot-Random + message),
#     Header X-Nextcloud-Talk-Bot-Random / X-Nextcloud-Talk-Bot-Signature.
#   - Bot-Registrierung geht NUR per "occ talk:bot:install" auf dem
#     Nextcloud-Host selbst (keine REST-Route), siehe README/Deploy-Notiz.
#
# WICHTIG: Die genauen Feldnamen im Webhook-Payload (actor/object/target) sind
# aus der Doku rekonstruiert, aber nicht live gegen edaphos verifiziert — beim
# ersten echten Test unbedingt `journalctl -u nc-talk-bot` prüfen und
# RAW_PAYLOAD_LOG bei Bedarf auf "true" setzen, um den echten Payload zu sehen
# und _extract_message() ggf. anzupassen.

import hashlib
import hmac
import json
import logging
import os
import secrets
import time

import httpx
from fastapi import FastAPI, Header, Request, Response

logger = logging.getLogger("nc-talk-bot")
logging.basicConfig(level=logging.INFO)

BOT_SECRET = os.environ["NC_TALK_BOT_SECRET"]
BOT_NAME = os.environ.get("NC_TALK_BOT_NAME", "kaira")

NEXTCLOUD_HOST = os.environ["NEXTCLOUD_HOST"].rstrip("/")
NEXTCLOUD_USERNAME = os.environ["NEXTCLOUD_USERNAME"]
NEXTCLOUD_PASSWORD = os.environ["NEXTCLOUD_PASSWORD"]
ALLOWED_GROUP = os.environ.get("NC_TALK_BOT_ALLOWED_GROUP", "wfd_aibot")

AGENT_URL = os.environ.get("KAIRA_URL", "http://127.0.0.1:3010/v1/chat/completions")
AGENT_API_KEY = os.environ["KAIRA_API_KEY"]
AGENT_MODEL = os.environ.get("KAIRA_MODEL", "claude-haiku-4-5-20251001")
AGENT_TIMEOUT = float(os.environ.get("KAIRA_TIMEOUT", "180"))

RAW_PAYLOAD_LOG = os.environ.get("RAW_PAYLOAD_LOG", "false").lower() == "true"

GROUP_CACHE_TTL = 300  # 5 Minuten
ROOM_TYPE_CACHE_TTL = 300

_group_members_cache: dict = {"members": set(), "fetched_at": 0.0}
_room_type_cache: dict = {}

NC_AUTH = (NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)
OCS_HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


def _verify_signature(secret: str, random_header: str, body: bytes, signature_header: str) -> bool:
    expected = hmac.new(secret.encode(), random_header.encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.lower())


async def _allowed_group_members() -> set:
    now = time.time()
    if now - _group_members_cache["fetched_at"] < GROUP_CACHE_TTL:
        return _group_members_cache["members"]

    url = f"{NEXTCLOUD_HOST}/ocs/v1.php/cloud/groups/{ALLOWED_GROUP}/users"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, auth=NC_AUTH, headers=OCS_HEADERS)
        resp.raise_for_status()
        members = set(resp.json()["ocs"]["data"]["users"])

    _group_members_cache["members"] = members
    _group_members_cache["fetched_at"] = now
    logger.info("Allowlist '%s' aktualisiert: %d Mitglieder", ALLOWED_GROUP, len(members))
    return members


async def _is_one_to_one(token: str) -> bool:
    now = time.time()
    cached = _room_type_cache.get(token)
    if cached and now - cached[1] < ROOM_TYPE_CACHE_TTL:
        return cached[0]

    url = f"{NEXTCLOUD_HOST}/ocs/v2.php/apps/spreed/api/v4/room/{token}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, auth=NC_AUTH, headers=OCS_HEADERS)
        resp.raise_for_status()
        room_type = resp.json()["ocs"]["data"]["type"]

    is_dm = room_type == 1  # 1 = one-to-one, siehe Talk-API-Doku "Conversation types"
    _room_type_cache[token] = (is_dm, now)
    return is_dm


def _extract_message(payload: dict) -> tuple[str, str, str] | None:
    """Gibt (actor_id, room_token, message_text) zurück, oder None wenn kein
    relevantes Ereignis (z.B. Reaction statt neue Nachricht)."""
    if payload.get("type") != "Create":
        return None

    actor = payload.get("actor", {})
    if actor.get("type") != "users":
        return None  # Bots/Gäste/Guests ignorieren

    obj = payload.get("object", {})
    content_raw = obj.get("content", "{}")
    content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
    message_text = content.get("message", "")

    target = payload.get("target", {})
    room_token = target.get("id", "")

    if not (actor.get("id") and room_token and message_text):
        return None

    return actor["id"], room_token, message_text


def _is_mentioned(payload: dict, message_text: str) -> bool:
    obj = payload.get("object", {})
    content_raw = obj.get("content", "{}")
    content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
    params = content.get("parameters", {}) or {}
    for p in params.values():
        if p.get("type") == "user" and p.get("mention-id") == BOT_NAME:
            return True
        if p.get("type") == "call" and p.get("mention-id") == "current-call":
            continue
    return f"@{BOT_NAME}" in message_text.lower()


async def _ask_kaira(message_text: str) -> str:
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            AGENT_URL,
            headers={"Authorization": f"Bearer {AGENT_API_KEY}"},
            json={
                "model": AGENT_MODEL,
                "messages": [{"role": "user", "content": message_text}],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _reply(room_token: str, message_text: str) -> None:
    random_header = secrets.token_hex(32)
    signature = hmac.new(
        BOT_SECRET.encode(), (random_header + message_text).encode(), hashlib.sha256
    ).hexdigest()

    url = f"{NEXTCLOUD_HOST}/ocs/v2.php/apps/spreed/api/v1/bot/{room_token}/message"
    headers = {
        **OCS_HEADERS,
        "X-Nextcloud-Talk-Bot-Random": random_header,
        "X-Nextcloud-Talk-Bot-Signature": signature,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json={"message": message_text})
        resp.raise_for_status()


@app.post("/webhook")
async def webhook(
    request: Request,
    x_nextcloud_talk_random: str = Header(default=""),
    x_nextcloud_talk_signature: str = Header(default=""),
):
    body = await request.body()

    if not x_nextcloud_talk_random or not x_nextcloud_talk_signature:
        return Response(status_code=401)
    if not _verify_signature(BOT_SECRET, x_nextcloud_talk_random, body, x_nextcloud_talk_signature):
        logger.warning("Signatur-Verifikation fehlgeschlagen — Request verworfen")
        return Response(status_code=401)

    if RAW_PAYLOAD_LOG:
        logger.info("Webhook-Payload: %s", body.decode(errors="replace"))

    payload = json.loads(body)
    extracted = _extract_message(payload)
    if extracted is None:
        return Response(status_code=200)  # kein relevantes Event, still ignorieren

    actor_id, room_token, message_text = extracted

    allowed = await _allowed_group_members()
    if actor_id not in allowed:
        return Response(status_code=200)  # nicht in wfd_aibot -> stillschweigend ignorieren

    dm = await _is_one_to_one(room_token)
    if not dm and not _is_mentioned(payload, message_text):
        return Response(status_code=200)  # Gruppenchat ohne @kaira-Erwähnung -> ignorieren

    try:
        answer = await _ask_kaira(message_text)
        await _reply(room_token, answer)
    except Exception:
        logger.exception("Fehler beim Verarbeiten der Nachricht von %s in %s", actor_id, room_token)
        # Bewusst kein Fehler an Nextcloud zurückmelden (Retry-Sturm vermeiden) —
        # der Fehler steht im Log.

    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("NC_TALK_BOT_PORT", "3012")))
