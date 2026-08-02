#!/usr/bin/env python3
"""fuchs-discord — Discord Bot + MCP Server auf darwin26 (Port 8011).

Zwei Aufgaben in einem Prozess:
1. Discord Gateway: Empfängt DMs/Kanal-Nachrichten → leitet an Sojus-Core weiter
2. FastMCP HTTP Server: Gibt Sojus Tools zum aktiven Schreiben/Lesen auf Discord
"""

import os
import asyncio
import logging
import httpx
import discord
from fastmcp import FastMCP

# ── Konfiguration ─────────────────────────────────────────────────────────────

TOKEN         = os.environ["DISCORD_BOT_TOKEN"]
SOJUS_URL     = os.environ.get("SOJUS_CORE_URL",   "http://127.0.0.1:3001")
SOJUS_API_KEY = os.environ.get("SOJUS_PIPELINE_KEY", "sojus-pipeline-key")
ALLOWED_USERS = set(os.environ.get("DISCORD_ALLOWED_USERS", "").split(",")) - {""}
PORT          = int(os.environ.get("DISCORD_MCP_PORT", "8011"))

log = logging.getLogger("fuchs-discord")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Discord Bot ───────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages     = True

bot = discord.Client(intents=intents)


async def _ask_sojus(user: str, text: str, channel_id: int) -> str:
    """Nachricht an Sojus-Core schicken und Antwort holen."""
    payload = {
        "model": "sojus-agent",
        "messages": [
            {"role": "user", "content": f"[Discord von {user}] {text}"},
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SOJUS_URL}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {SOJUS_API_KEY}"},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.error("Sojus-Core nicht erreichbar: %s", e)
        return f"⚠️ Sojus antwortet gerade nicht: {e}"


def _split(text: str, limit: int = 1990) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, rest = [], text
    while rest:
        cut = rest.rfind("\n", 0, limit) if len(rest) > limit else len(rest)
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    return chunks


@bot.event
async def on_ready() -> None:
    log.info("Discord Bot online als %s", bot.user)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    mentioned = bot.user in message.mentions if bot.user else False

    if not is_dm and not mentioned:
        return

    # User-Allowlist prüfen
    if ALLOWED_USERS and str(message.author.id) not in ALLOWED_USERS:
        log.info("Nicht autorisierter User %s ignoriert", message.author.id)
        return

    async with message.channel.typing():
        reply = await _ask_sojus(
            user=message.author.display_name,
            text=message.clean_content,
            channel_id=message.channel.id,
        )

    for chunk in _split(reply):
        await message.channel.send(chunk)

# ── FastMCP Tools ─────────────────────────────────────────────────────────────

mcp = FastMCP(
    "fuchs-discord",
    instructions=(
        "Discord-Zugriff für Sojus. Verwende send_message um Nachrichten zu senden. "
        "Kanäle und DMs werden über ihre ID angesprochen. "
        "get_messages gibt die letzten N Nachrichten zurück (älteste zuerst)."
    ),
)


def _bot_ready() -> discord.Client:
    if not bot.is_ready():
        raise RuntimeError("Discord Bot noch nicht verbunden")
    return bot


@mcp.tool()
async def discord_send_message(channel_id: str, text: str) -> str:
    """Nachricht in einen Discord-Kanal oder eine DM senden."""
    b = _bot_ready()
    channel = b.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await b.fetch_channel(int(channel_id))
        except Exception as e:
            return f"Kanal {channel_id} nicht gefunden: {e}"

    sent = []
    for chunk in _split(text):
        msg = await channel.send(chunk)
        sent.append(msg.id)
    return f"Gesendet (IDs: {sent})"


@mcp.tool()
async def discord_get_messages(channel_id: str, limit: int = 20) -> list[dict]:
    """Letzte Nachrichten aus einem Kanal lesen (max 100, älteste zuerst)."""
    b = _bot_ready()
    channel = b.get_channel(int(channel_id))
    if channel is None:
        channel = await b.fetch_channel(int(channel_id))

    msgs = []
    async for m in channel.history(limit=min(limit, 100)):
        msgs.append({
            "id":      str(m.id),
            "author":  m.author.display_name,
            "content": m.clean_content,
            "ts":      m.created_at.isoformat(),
        })
    return list(reversed(msgs))


@mcp.tool()
async def discord_add_reaction(channel_id: str, message_id: str, emoji: str) -> str:
    """Emoji-Reaktion auf eine Nachricht hinzufügen."""
    b = _bot_ready()
    channel = b.get_channel(int(channel_id)) or await b.fetch_channel(int(channel_id))
    message = await channel.fetch_message(int(message_id))
    await message.add_reaction(emoji)
    return "Reaktion hinzugefügt"


@mcp.tool()
async def discord_list_guilds() -> list[dict]:
    """Server (Guilds) auflisten, in denen der Bot Mitglied ist."""
    b = _bot_ready()
    return [{"id": str(g.id), "name": g.name, "members": g.member_count} for g in b.guilds]


@mcp.tool()
async def discord_list_channels(guild_id: str) -> list[dict]:
    """Text-Kanäle eines Servers auflisten."""
    b = _bot_ready()
    guild = b.get_guild(int(guild_id))
    if guild is None:
        guild = await b.fetch_guild(int(guild_id))
    return [
        {"id": str(c.id), "name": c.name, "type": str(c.type)}
        for c in guild.channels
        if isinstance(c, (discord.TextChannel, discord.DMChannel))
    ]


# ── Main: Bot + MCP parallel starten ─────────────────────────────────────────

async def _main() -> None:
    mcp_task     = asyncio.create_task(
        mcp.run_async(transport="streamable-http", host="0.0.0.0", port=PORT)
    )
    discord_task = asyncio.create_task(bot.start(TOKEN))

    log.info("Starte Discord Bot + MCP Server (Port %d)...", PORT)
    try:
        await asyncio.gather(mcp_task, discord_task)
    except Exception as e:
        log.error("Fehler: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(_main())
