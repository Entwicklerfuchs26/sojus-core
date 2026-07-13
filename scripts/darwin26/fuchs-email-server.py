#!/usr/bin/env python3
"""fuchs-email — E-Mail MCP Server auf darwin26 (Port 8013).

Drei Accounts über mail.your-server.de:
  jonas@hofpause.info
  jonas.tuerk@arteigen.de
  jonas.tuerk@weites-feld.org

SMTP: Port 465 SSL/TLS (senden)
IMAP: Port 993 SSL/TLS (lesen)
"""

import os
import smtplib
import imaplib
import email
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from fastmcp import FastMCP

# ── Konfiguration ─────────────────────────────────────────────────────────────

SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "mail.your-server.de")
SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "465"))
IMAP_HOST = os.environ.get("EMAIL_IMAP_HOST", "mail.your-server.de")
IMAP_PORT = int(os.environ.get("EMAIL_IMAP_PORT", "993"))

# Accounts: Adresse → Passwort (separate Env-Vars pro Account)
ACCOUNTS: dict[str, str] = {}
for addr, env_key in [
    ("jonas@hofpause.info",         "EMAIL_PASS_HOFPAUSE"),
    ("jonas.tuerk@arteigen.de",     "EMAIL_PASS_ARTEIGEN"),
    ("jonas.tuerk@weites-feld.org", "EMAIL_PASS_WEITES_FELD"),
]:
    pw = os.environ.get(env_key, "")
    if pw:
        ACCOUNTS[addr] = pw

DEFAULT_FROM = os.environ.get("EMAIL_DEFAULT_FROM", "jonas@hofpause.info")

PORT = int(os.environ.get("EMAIL_MCP_PORT", "8013"))

mcp = FastMCP(
    "fuchs-email",
    instructions=(
        "E-Mail-Zugriff für Jonas über mail.your-server.de. "
        f"Verfügbare Absender-Adressen: {', '.join(ACCOUNTS.keys()) or 'keine konfiguriert'}. "
        "Standard-Absender: " + DEFAULT_FROM + ". "
        "Zum Senden: email_send. Zum Lesen: email_list_inbox, email_get_message. "
        "Zum Suchen: email_search."
    ),
)


def _decode_header_str(h: str) -> str:
    parts = decode_header(h or "")
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _get_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")[:4000]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")[:4000]
    return ""


def _smtp_send(from_addr: str, to: str, subject: str, body: str) -> None:
    pw = ACCOUNTS.get(from_addr)
    if not pw:
        raise ValueError(f"Kein Passwort für {from_addr} konfiguriert")

    msg = MIMEMultipart("alternative")
    msg["From"]    = from_addr
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(from_addr, pw)
        s.sendmail(from_addr, [to], msg.as_string())


def _imap_connect(address: str) -> imaplib.IMAP4_SSL:
    pw = ACCOUNTS.get(address)
    if not pw:
        raise ValueError(f"Kein Passwort für {address} konfiguriert")
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(address, pw)
    return conn


def _fetch_messages(conn: imaplib.IMAP4_SSL, uids: list[bytes], preview: bool = True) -> list[dict]:
    results = []
    for uid in uids:
        typ, data = conn.fetch(uid, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            continue
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw)
        entry = {
            "uid":     uid.decode(),
            "from":    _decode_header_str(msg.get("From", "")),
            "to":      _decode_header_str(msg.get("To", "")),
            "subject": _decode_header_str(msg.get("Subject", "")),
            "date":    msg.get("Date", ""),
        }
        if not preview:
            entry["body"] = _get_body(msg)
        else:
            entry["preview"] = _get_body(msg)[:200]
        results.append(entry)
    return results


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def email_send(to: str, subject: str, body: str, from_address: str = "") -> str:
    """E-Mail senden. from_address leer lassen für Standard-Absender (jonas@hofpause.info)."""
    sender = from_address or DEFAULT_FROM
    if sender not in ACCOUNTS:
        return f"Fehler: Unbekannte Absenderadresse '{sender}'. Verfügbar: {list(ACCOUNTS.keys())}"
    try:
        _smtp_send(sender, to, subject, body)
        return f"E-Mail gesendet: {sender} → {to} | Betreff: {subject}"
    except Exception as e:
        return f"Fehler beim Senden: {e}"


@mcp.tool()
def email_list_inbox(address: str = "", limit: int = 20, unread_only: bool = False) -> list[dict]:
    """Posteingang eines Accounts auflisten (neueste zuerst). address leer = Standard-Account."""
    account = address or DEFAULT_FROM
    try:
        conn = _imap_connect(account)
        conn.select("INBOX")
        criterion = "UNSEEN" if unread_only else "ALL"
        typ, data = conn.search(None, criterion)
        if typ != "OK":
            return [{"error": "IMAP search fehlgeschlagen"}]
        uids = data[0].split()
        uids = uids[-limit:][::-1]  # neueste zuerst
        result = _fetch_messages(conn, uids, preview=True)
        conn.logout()
        return result
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def email_get_message(uid: str, address: str = "") -> dict:
    """Vollständige E-Mail anhand ihrer UID laden (inkl. Body)."""
    account = address or DEFAULT_FROM
    try:
        conn = _imap_connect(account)
        conn.select("INBOX")
        result = _fetch_messages(conn, [uid.encode()], preview=False)
        conn.logout()
        return result[0] if result else {"error": f"UID {uid} nicht gefunden"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def email_search(query: str, address: str = "", limit: int = 10) -> list[dict]:
    """E-Mails suchen. query ist ein IMAP-Suchbegriff, z.B. 'SUBJECT "Rechnung"' oder 'FROM "example.com"'."""
    account = address or DEFAULT_FROM
    try:
        conn = _imap_connect(account)
        conn.select("INBOX")
        typ, data = conn.search(None, query)
        if typ != "OK":
            return [{"error": "Suche fehlgeschlagen"}]
        uids = data[0].split()[-limit:][::-1]
        result = _fetch_messages(conn, uids, preview=True)
        conn.logout()
        return result
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def email_list_accounts() -> list[str]:
    """Alle konfigurierten E-Mail-Accounts auflisten."""
    return list(ACCOUNTS.keys())


@mcp.tool()
def email_mark_read(uid: str, address: str = "") -> str:
    """E-Mail als gelesen markieren."""
    account = address or DEFAULT_FROM
    try:
        conn = _imap_connect(account)
        conn.select("INBOX")
        conn.store(uid.encode(), "+FLAGS", "\\Seen")
        conn.logout()
        return f"UID {uid} als gelesen markiert"
    except Exception as e:
        return f"Fehler: {e}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
