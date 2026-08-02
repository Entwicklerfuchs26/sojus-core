#!/usr/bin/env python3
"""Sojus Supplement MCP Server — Aktivität, Ankündigungen, Polls, Formulare"""

import os
import json
import httpx
from fastmcp import FastMCP

NC_HOST = os.environ["NEXTCLOUD_HOST"]
NC_USER = os.environ["NEXTCLOUD_USERNAME"]
NC_PASS = os.environ["NEXTCLOUD_PASSWORD"]
OCS_HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}

mcp = FastMCP(
    "sojus-supplement",
    instructions="Nextcloud Supplement Tools: Aktivität, Ankündigungen, Polls, Formulare auf edaphos.weites-feld.org"
)


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{NC_HOST}{path}",
            auth=(NC_USER, NC_PASS),
            headers=OCS_HEADERS,
            params=params or {},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{NC_HOST}{path}",
            auth=(NC_USER, NC_PASS),
            headers={**OCS_HEADERS, "Content-Type": "application/json"},
            json=data or {},
            params=params or {},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


async def _delete(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{NC_HOST}{path}",
            auth=(NC_USER, NC_PASS),
            headers=OCS_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


def _ocs_data(response: dict) -> dict | list:
    return response["ocs"]["data"]


# ─── AKTIVITÄT ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def nc_activity_list(
    limit: int = 50,
    since: int = 0,
    activity_type: str = "",
    sort: str = "desc",
    object_type: str = "",
    object_id: int = 0,
) -> str:
    """Listet die letzten Nextcloud-Aktivitäten auf (Dateiänderungen, Kalender, Talk, etc.)

    Args:
        limit: Maximale Anzahl Aktivitäten (Standard: 50)
        since: Nur Aktivitäten nach dieser Activity-ID (für Pagination)
        activity_type: Filter auf Aktivitätstyp (z.B. 'file_created', 'calendar_event', 'files')
        sort: Sortierung 'desc' (neueste zuerst) oder 'asc'
        object_type: Nur Aktivitäten für diesen Objekttyp (z.B. 'files', 'calendar')
        object_id: Nur Aktivitäten für dieses spezifische Objekt (Datei-ID etc.)
    """
    params: dict = {"limit": limit, "sort": sort, "format": "json"}
    if since:
        params["since"] = since
    if activity_type:
        params["type"] = activity_type
    if object_type:
        params["object_type"] = object_type
    if object_id:
        params["object_id"] = object_id

    data = await _get("/ocs/v2.php/apps/activity/api/v2/activity/all", params)
    activities = _ocs_data(data)

    if not activities:
        return "Keine Aktivitäten gefunden."

    lines = []
    for a in activities:
        ts = a.get("datetime", a.get("timestamp", ""))
        subj = a.get("subject", "")
        atype = a.get("type", "")
        lines.append(f"[{ts}] [{atype}] {subj}")

    return "\n".join(lines)


# ─── ANKÜNDIGUNGEN ─────────────────────────────────────────────────────────────

@mcp.tool()
async def nc_announcements_list() -> str:
    """Listet alle Nextcloud-Ankündigungen (Announcement Center App)"""
    data = await _get("/ocs/v2.php/apps/announcementcenter/api/v1/announcements", {"format": "json"})
    announcements = _ocs_data(data)

    if not announcements:
        return "Keine Ankündigungen vorhanden."

    lines = []
    for a in announcements:
        aid = a.get("id", "")
        subject = a.get("subject", "")
        author = a.get("authorDisplayName", a.get("author", ""))
        ts = a.get("time", "")
        lines.append(f"[{aid}] {subject} (von {author}, {ts})")

    return "\n".join(lines)


@mcp.tool()
async def nc_announcements_create(
    subject: str,
    message: str,
    groups: list[str] | None = None,
    send_notifications: bool = True,
    create_activities: bool = True,
    allow_comments: bool = True,
) -> str:
    """Erstellt eine neue Nextcloud-Ankündigung (erfordert Admin-Rechte)

    Args:
        subject: Betreff der Ankündigung
        message: Nachrichtentext (Markdown unterstützt)
        groups: Liste der Zielgruppen (leer = alle)
        send_notifications: Push-Notification senden
        create_activities: Aktivitätseintrag erstellen
        allow_comments: Kommentare erlauben
    """
    payload = {
        "subject": subject,
        "message": message,
        "plainMessage": message,
        "createActivities": create_activities,
        "createNotifications": send_notifications,
        "sendEmails": False,
        "groups": groups or [],
        "comments": allow_comments,
    }
    data = await _post(
        "/ocs/v2.php/apps/announcementcenter/api/v1/announcements",
        data=payload,
        params={"format": "json"},
    )
    result = _ocs_data(data)
    return f"Ankündigung erstellt: ID {result.get('id', '?')} – {result.get('subject', subject)}"


@mcp.tool()
async def nc_announcements_delete(announcement_id: int) -> str:
    """Löscht eine Nextcloud-Ankündigung (erfordert Admin-Rechte)

    Args:
        announcement_id: ID der Ankündigung (aus nc_announcements_list)
    """
    await _delete(
        f"/ocs/v2.php/apps/announcementcenter/api/v1/announcements/{announcement_id}"
    )
    return f"Ankündigung {announcement_id} gelöscht."


# ─── POLLS (UMFRAGEN) ──────────────────────────────────────────────────────────

@mcp.tool()
async def nc_polls_list(filter: str = "relevant") -> str:
    """Listet Nextcloud-Polls (Umfragen).

    Args:
        filter: 'relevant' (Standard), 'my', 'participated', 'open', 'closed', 'archived', 'all'
    """
    data = await _get("/ocs/v2.php/apps/polls/api/v1.0/polls", {"format": "json"})
    all_polls = _ocs_data(data).get("polls", [])

    if filter == "my":
        polls = [p for p in all_polls if p["currentUserStatus"].get("isOwner")]
    elif filter == "participated":
        polls = [p for p in all_polls if p["currentUserStatus"].get("countVotes", 0) > 0]
    elif filter == "open":
        polls = [p for p in all_polls if not p["status"].get("isArchived") and not p["status"].get("isExpired")]
    elif filter == "closed":
        polls = [p for p in all_polls if p["status"].get("isExpired")]
    elif filter == "archived":
        polls = [p for p in all_polls if p["status"].get("isArchived")]
    else:
        polls = all_polls

    if not polls:
        return f"Keine Polls unter Filter '{filter}' gefunden."

    lines = []
    for p in polls:
        cfg = p["configuration"]
        status = p["status"]
        pid = p["id"]
        title = cfg["title"]
        ptype = p["type"]
        participants = status.get("countParticipants", 0)
        owner = p["owner"].get("displayName", "?")
        archived = " [archiviert]" if status.get("isArchived") else ""
        lines.append(f"[{pid}] {title} (Typ: {ptype}, {participants} Teilnehmer, Ersteller: {owner}){archived}")

    return f"{len(polls)} Poll(s):\n" + "\n".join(lines)


@mcp.tool()
async def nc_polls_get(poll_id: int) -> str:
    """Zeigt Details und Abstimmungsoptionen eines spezifischen Polls.

    Args:
        poll_id: ID des Polls (aus nc_polls_list)
    """
    poll_data = await _get(f"/ocs/v2.php/apps/polls/api/v1.0/poll/{poll_id}", {"format": "json"})
    poll = _ocs_data(poll_data).get("poll", {})

    options_data = await _get(f"/ocs/v2.php/apps/polls/api/v1.0/poll/{poll_id}/options", {"format": "json"})
    options = _ocs_data(options_data).get("options", [])

    cfg = poll.get("configuration", {})
    status = poll.get("status", {})

    lines = [
        f"Titel: {cfg.get('title', '?')}",
        f"Beschreibung: {cfg.get('description', '-')[:200]}",
        f"Typ: {poll.get('type', '?')}",
        f"Zugang: {cfg.get('access', '?')}",
        f"Teilnehmer: {status.get('countParticipants', 0)}",
        f"Kommentare erlaubt: {cfg.get('allowComment', False)}",
        f"Vielleicht erlaubt: {cfg.get('allowMaybe', False)}",
        f"",
        f"Optionen ({len(options)}):",
    ]
    for opt in options:
        oid = opt.get("id", "?")
        text = opt.get("text", opt.get("timestamp", "?"))
        lines.append(f"  [{oid}] {text}")

    return "\n".join(lines)


@mcp.tool()
async def nc_polls_get_votes(poll_id: int) -> str:
    """Zeigt alle Stimmen für einen Poll.

    Args:
        poll_id: ID des Polls
    """
    data = await _get(f"/ocs/v2.php/apps/polls/api/v1.0/poll/{poll_id}/votes", {"format": "json"})
    votes = _ocs_data(data).get("votes", [])

    if not votes:
        return "Noch keine Stimmen abgegeben."

    lines = [f"{len(votes)} Stimme(n):"]
    for v in votes:
        user = v.get("user", {}).get("displayName", "?")
        option_text = v.get("optionText", "?")
        answer = v.get("answer", "?")
        lines.append(f"  {user}: [{option_text}] → {answer}")

    return "\n".join(lines)


@mcp.tool()
async def nc_polls_vote(option_id: int, answer: str = "yes") -> str:
    """Gibt eine Stimme für eine Poll-Option ab.

    Args:
        option_id: ID der Option (aus nc_polls_get)
        answer: 'yes' (Ja), 'no' (Nein) oder 'maybe' (Vielleicht)
    """
    if answer not in ("yes", "no", "maybe"):
        return "Ungültige Antwort. Erlaubt: 'yes', 'no', 'maybe'"

    data = await _post(
        "/ocs/v2.php/apps/polls/api/v1.0/vote",
        data={"optionId": option_id, "setTo": answer},
        params={"format": "json"},
    )
    result = _ocs_data(data)
    return f"Stimme abgegeben: Option {option_id} → {answer}"


# ─── FORMULARE ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def nc_forms_list() -> str:
    """Listet alle Nextcloud-Formulare (Forms App)."""
    data = await _get("/ocs/v2.php/apps/forms/api/v3/forms", {"format": "json"})
    forms = _ocs_data(data)

    if not forms:
        return "Keine Formulare gefunden."

    lines = []
    for f in forms:
        fid = f.get("id", "?")
        fhash = f.get("hash", "?")
        title = f.get("title", "?")
        count = f.get("submissionCount", 0)
        state = "offen" if f.get("state", 0) == 0 else "geschlossen"
        lines.append(f"[{fid}] {title} (Hash: {fhash}, {count} Einträge, {state})")

    return f"{len(forms)} Formular(e):\n" + "\n".join(lines)


@mcp.tool()
async def nc_forms_get(form_id: int) -> str:
    """Zeigt Details und Fragen eines Formulars.

    Args:
        form_id: ID des Formulars (aus nc_forms_list)
    """
    data = await _get(f"/ocs/v2.php/apps/forms/api/v3/forms/{form_id}", {"format": "json"})
    form = _ocs_data(data)

    title = form.get("title", "?")
    description = form.get("description", "")
    fhash = form.get("hash", "?")
    state = "offen" if form.get("state", 0) == 0 else "geschlossen"
    questions = form.get("questions", [])

    lines = [
        f"Titel: {title}",
        f"Beschreibung: {description[:200] if description else '-'}",
        f"Hash: {fhash}",
        f"Status: {state}",
        f"Eingaben: {form.get('submissionCount', 0)}",
        f"",
        f"Fragen ({len(questions)}):",
    ]
    for q in questions:
        qid = q.get("id", "?")
        qtype = q.get("type", "?")
        qtext = q.get("text", "?")
        required = " *" if q.get("isRequired") else ""
        lines.append(f"  [{qid}] ({qtype}) {qtext}{required}")
        for opt in q.get("options", []):
            lines.append(f"    • {opt.get('text', '?')}")

    return "\n".join(lines)


@mcp.tool()
async def nc_forms_get_submissions(form_hash: str) -> str:
    """Zeigt alle Einträge/Antworten eines Formulars.

    Args:
        form_hash: Hash des Formulars (aus nc_forms_list oder nc_forms_get)
    """
    data = await _get(
        f"/ocs/v2.php/apps/forms/api/v3/submissions/{form_hash}",
        {"format": "json"},
    )
    payload = _ocs_data(data)

    submissions = payload.get("submissions", [])
    questions = {q["id"]: q["text"] for q in payload.get("questions", [])}

    if not submissions:
        return "Noch keine Einträge vorhanden."

    lines = [f"{len(submissions)} Eintrag/Einträge:"]
    for sub in submissions:
        user = sub.get("userDisplayName", sub.get("userId", "anonym"))
        ts = sub.get("timestamp", "")
        lines.append(f"\n  [{ts}] {user}:")
        for ans in sub.get("answers", []):
            qid = ans.get("questionId")
            qtext = questions.get(qid, f"Frage {qid}")
            value = ans.get("text", "")
            lines.append(f"    {qtext}: {value}")

    return "\n".join(lines)


# ───────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", "8001"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    mcp.run(transport="streamable-http", host=host, port=port)
