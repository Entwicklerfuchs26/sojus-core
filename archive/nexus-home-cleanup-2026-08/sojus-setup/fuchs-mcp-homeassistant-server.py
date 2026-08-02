import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-homeassistant",
    instructions="Vollständige Home Assistant Steuerung auf darwin26: Entities, Automationen, Szenen, Scripts, Push-Notifications, Verlauf, Templates",
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


# ── ZUSTÄNDE & ENTITIES ───────────────────────────────────────────────────────

@mcp.tool()
def ha_get_state(entity_id: str) -> dict:
    """Zustand einer Entity abrufen (z.B. 'light.wohnzimmer', 'sensor.temperatur')."""
    return api("GET", f"/states/{entity_id}")

@mcp.tool()
def ha_list_states(domain: str = "") -> list:
    """Alle Entities auflisten. domain filtert optional (z.B. 'light', 'switch', 'sensor', 'climate', 'media_player')."""
    states = api("GET", "/states")
    if domain:
        return [s for s in states if s["entity_id"].startswith(f"{domain}.")]
    return states

@mcp.tool()
def ha_set_state(entity_id: str, state: str, attributes: dict | None = None) -> dict:
    """Zustand einer Entity manuell setzen (nur HA-intern, steuert kein Gerät)."""
    body: dict = {"state": state}
    if attributes:
        body["attributes"] = attributes
    return api("POST", f"/states/{entity_id}", json=body)


# ── STEUERUNG ─────────────────────────────────────────────────────────────────

@mcp.tool()
def ha_call_service(domain: str, service: str, entity_id: str = "", data: dict | None = None) -> list:
    """Beliebigen HA-Service aufrufen. Beispiele: domain='light' service='turn_on', domain='climate' service='set_temperature'."""
    body: dict = data or {}
    if entity_id:
        body["entity_id"] = entity_id
    return api("POST", f"/services/{domain}/{service}", json=body)

@mcp.tool()
def ha_turn_on(
    entity_id: str,
    brightness: int | None = None,
    color_temp: int | None = None,
    rgb_color: list | None = None,
    effect: str | None = None,
) -> list:
    """Entity einschalten. Für Lichter optional: brightness (0-255), color_temp (Mireds), rgb_color ([R,G,B]), effect."""
    domain = entity_id.split(".")[0]
    body: dict = {"entity_id": entity_id}
    if brightness is not None:
        body["brightness"] = brightness
    if color_temp is not None:
        body["color_temp"] = color_temp
    if rgb_color is not None:
        body["rgb_color"] = rgb_color
    if effect is not None:
        body["effect"] = effect
    return api("POST", f"/services/{domain}/turn_on", json=body)

@mcp.tool()
def ha_turn_off(entity_id: str) -> list:
    """Entity ausschalten."""
    domain = entity_id.split(".")[0]
    return api("POST", f"/services/{domain}/turn_off", json={"entity_id": entity_id})

@mcp.tool()
def ha_toggle(entity_id: str) -> list:
    """Entity ein-/ausschalten (toggle)."""
    domain = entity_id.split(".")[0]
    return api("POST", f"/services/{domain}/toggle", json={"entity_id": entity_id})


# ── AUTOMATIONEN ──────────────────────────────────────────────────────────────

@mcp.tool()
def ha_list_automations() -> list:
    """Alle Automationen auflisten."""
    return [s for s in api("GET", "/states") if s["entity_id"].startswith("automation.")]

@mcp.tool()
def ha_trigger_automation(entity_id: str) -> dict:
    """Automation manuell auslösen."""
    return api("POST", "/services/automation/trigger", json={"entity_id": entity_id})

@mcp.tool()
def ha_enable_automation(entity_id: str) -> dict:
    """Automation aktivieren."""
    return api("POST", "/services/automation/turn_on", json={"entity_id": entity_id})

@mcp.tool()
def ha_disable_automation(entity_id: str) -> dict:
    """Automation deaktivieren."""
    return api("POST", "/services/automation/turn_off", json={"entity_id": entity_id})


# ── SZENEN ────────────────────────────────────────────────────────────────────

@mcp.tool()
def ha_list_scenes() -> list:
    """Alle Szenen auflisten."""
    return [s for s in api("GET", "/states") if s["entity_id"].startswith("scene.")]

@mcp.tool()
def ha_activate_scene(entity_id: str) -> dict:
    """Szene aktivieren."""
    return api("POST", "/services/scene/turn_on", json={"entity_id": entity_id})


# ── SCRIPTS ───────────────────────────────────────────────────────────────────

@mcp.tool()
def ha_list_scripts() -> list:
    """Alle Scripts auflisten."""
    return [s for s in api("GET", "/states") if s["entity_id"].startswith("script.")]

@mcp.tool()
def ha_run_script(entity_id: str) -> dict:
    """Script ausführen."""
    script_name = entity_id.replace("script.", "")
    return api("POST", f"/services/script/{script_name}", json={})


# ── BEREICHE (AREAS) ──────────────────────────────────────────────────────────

@mcp.tool()
def ha_list_areas() -> list:
    """Alle Bereiche (Räume) auflisten."""
    resp = api("POST", "/template", json={"template": "{{ areas() | list }}"})
    return resp if isinstance(resp, list) else []


# ── INPUT HELPERS ─────────────────────────────────────────────────────────────

@mcp.tool()
def ha_input_boolean_set(entity_id: str, value: bool) -> dict:
    """Input Boolean setzen (true = turn_on, false = turn_off)."""
    service = "turn_on" if value else "turn_off"
    return api("POST", f"/services/input_boolean/{service}", json={"entity_id": entity_id})

@mcp.tool()
def ha_input_number_set(entity_id: str, value: float) -> dict:
    """Input Number setzen."""
    return api("POST", "/services/input_number/set_value", json={"entity_id": entity_id, "value": value})

@mcp.tool()
def ha_input_select_set(entity_id: str, option: str) -> dict:
    """Input Select Option auswählen."""
    return api("POST", "/services/input_select/select_option", json={"entity_id": entity_id, "option": option})

@mcp.tool()
def ha_input_text_set(entity_id: str, value: str) -> dict:
    """Input Text setzen."""
    return api("POST", "/services/input_text/set_value", json={"entity_id": entity_id, "value": value})


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
def ha_send_notification_critical(message: str, title: str = "", target: str = "") -> list:
    """Kritische iOS-Benachrichtigung (durchbricht Nicht-Stören-Modus)."""
    notify_target = target or NOTIFY_TARGET
    body: dict = {
        "message": message,
        "data": {"push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}}},
    }
    if title:
        body["title"] = title
    return api("POST", f"/services/notify/{notify_target}", json=body)

@mcp.tool()
def ha_list_persistent_notifications() -> list:
    """Persistente HA-Benachrichtigungen auflisten."""
    return [s for s in api("GET", "/states") if s["entity_id"].startswith("persistent_notification.")]

@mcp.tool()
def ha_dismiss_persistent_notification(notification_id: str) -> dict:
    """Persistente HA-Benachrichtigung entfernen."""
    return api("POST", "/services/persistent_notification/dismiss", json={"notification_id": notification_id})


# ── TEMPLATES & EVENTS ────────────────────────────────────────────────────────

@mcp.tool()
def ha_render_template(template: str) -> str:
    """Jinja2-Template in HA auswerten (z.B. '{{ states(\"sensor.temperature\") }}')."""
    result = api("POST", "/template", json={"template": template})
    return str(result)

@mcp.tool()
def ha_fire_event(event_type: str, event_data: dict | None = None) -> dict:
    """HA-Event auslösen."""
    return api("POST", f"/events/{event_type}", json=event_data or {})


# ── VERLAUF & LOGS ────────────────────────────────────────────────────────────

@mcp.tool()
def ha_get_history(entity_id: str, hours: int = 24) -> list:
    """Zustands-Verlauf einer Entity abrufen."""
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return api("GET", f"/history/period/{start}", params={"filter_entity_id": entity_id})

@mcp.tool()
def ha_get_logbook(hours: int = 12, entity_id: str = "") -> list:
    """Logbuch-Einträge abrufen."""
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    params = {}
    if entity_id:
        params["entity"] = entity_id
    return api("GET", f"/logbook/{start}", params=params)

@mcp.tool()
def ha_get_error_log() -> str:
    """HA Error-Log abrufen."""
    resp = httpx.get(f"{BASE_URL}/api/error_log", headers=HEADERS, timeout=30)
    return resp.text


# ── SYSTEM ────────────────────────────────────────────────────────────────────

@mcp.tool()
def ha_get_config() -> dict:
    """HA-Systemkonfiguration abrufen (Version, Standort, Zeitzone etc.)."""
    return api("GET", "/config")

@mcp.tool()
def ha_check_config() -> dict:
    """HA-Konfiguration auf Fehler prüfen."""
    return api("POST", "/config/core/check_config", json={})

@mcp.tool()
def ha_restart() -> dict:
    """Home Assistant neu starten. Nur bei Bedarf verwenden!"""
    return api("POST", "/services/homeassistant/restart", json={})
