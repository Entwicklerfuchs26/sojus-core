import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-homeassistant",
    instructions="Home Assistant Steuerung und iOS-Push-Benachrichtigungen auf darwin26",
)

BASE_URL = os.environ["HA_URL"].rstrip("/")
TOKEN = os.environ["HA_TOKEN"]
NOTIFY_TARGET = os.environ.get("HA_NOTIFY_TARGET", "mobile_app_iphone")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs):
    resp = httpx.request(method, f"{BASE_URL}/api{path}", headers=HEADERS, timeout=30, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204 or not resp.content:
        return {"success": True}
    return resp.json()


# ── ZUSTÄNDE ──────────────────────────────────────────────────────────────────

@mcp.tool()
def ha_get_state(entity_id: str) -> dict:
    """Zustand einer HA-Entity abrufen (z.B. 'light.wohnzimmer', 'sensor.temperatur')."""
    return api("GET", f"/states/{entity_id}")

@mcp.tool()
def ha_list_states(domain: str = "") -> list:
    """Alle Entity-Zustände auflisten. domain filtert optional (z.B. 'light', 'switch', 'sensor')."""
    states = api("GET", "/states")
    if domain:
        return [s for s in states if s["entity_id"].startswith(f"{domain}.")]
    return states


# ── STEUERUNG ─────────────────────────────────────────────────────────────────

@mcp.tool()
def ha_call_service(domain: str, service: str, entity_id: str = "", data: dict | None = None) -> list:
    """HA-Service aufrufen. Beispiele: domain='light' service='turn_on' entity_id='light.wohnzimmer'."""
    body: dict = data or {}
    if entity_id:
        body["entity_id"] = entity_id
    return api("POST", f"/services/{domain}/{service}", json=body)

@mcp.tool()
def ha_toggle(entity_id: str) -> list:
    """Entity ein-/ausschalten (toggle). Funktioniert für Lichter, Schalter etc."""
    domain = entity_id.split(".")[0]
    return api("POST", f"/services/{domain}/toggle", json={"entity_id": entity_id})


# ── BENACHRICHTIGUNGEN ────────────────────────────────────────────────────────

@mcp.tool()
def ha_send_notification(message: str, title: str = "", target: str = "") -> list:
    """iOS Push-Benachrichtigung über HA Companion App senden."""
    notify_target = target or NOTIFY_TARGET
    body: dict = {"message": message}
    if title:
        body["title"] = title
    return api("POST", f"/services/notify/{notify_target}", json=body)

@mcp.tool()
def ha_send_notification_with_action(
    message: str,
    title: str = "",
    action_url: str = "",
    target: str = "",
) -> list:
    """iOS Push mit Tap-Action (öffnet URL beim Antippen)."""
    notify_target = target or NOTIFY_TARGET
    body: dict = {"message": message}
    if title: body["title"] = title
    if action_url:
        body["data"] = {"url": action_url, "push": {"sound": "default"}}
    return api("POST", f"/services/notify/{notify_target}", json=body)


# ── VERLAUF & INFOS ───────────────────────────────────────────────────────────

@mcp.tool()
def ha_get_history(entity_id: str, hours: int = 24) -> list:
    """Zustands-Verlauf einer Entity abrufen (Standard: letzte 24h)."""
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return api("GET", f"/history/period/{start}", params={"filter_entity_id": entity_id})

@mcp.tool()
def ha_list_automations() -> list:
    """Alle Automationen auflisten."""
    return api("GET", "/config/automation/config")

@mcp.tool()
def ha_get_logbook(hours: int = 12) -> list:
    """Logbuch-Einträge der letzten Stunden abrufen."""
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return api("GET", f"/logbook/{start}")
