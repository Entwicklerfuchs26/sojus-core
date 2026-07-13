#!/usr/bin/env python3
"""
Stellarium MCP Server — wraps Stellarium RemoteControl HTTP API (port 8585).
Voraussetzung: Stellarium läuft mit aktivem RemoteControl-Plugin.
"""

import httpx
from fastmcp import FastMCP

URL = "http://127.0.0.1:8585"
mcp = FastMCP("Stellarium")


def _get(path: str, **params) -> dict | str:
    r = httpx.get(f"{URL}{path}", params=params, timeout=10)
    try:
        return r.json()
    except Exception:
        return r.text


def _post(path: str, data: dict | None = None) -> dict | str:
    r = httpx.post(f"{URL}{path}", data=data or {}, timeout=10)
    try:
        return r.json()
    except Exception:
        return r.text


@mcp.tool()
def stellarium_status() -> dict:
    """Aktuellen Stellarium-Status abrufen: Zeit, Ort, FoV, Darstellungsoptionen."""
    return _get("/api/main/status")


@mcp.tool()
def stellarium_focus(name: str) -> str:
    """Auf ein Himmelsobjekt fokussieren (z.B. 'Mars', 'Sirius', 'M31', 'ISS').
    Zentriert die Ansicht auf das Objekt und wählt es aus."""
    return _post("/api/main/focus", {"target": name})


@mcp.tool()
def stellarium_object_info(name: str) -> dict:
    """Detaillierte Informationen über ein Himmelsobjekt (Koordinaten, Helligkeit,
    Entfernung, Spektraltyp, etc.)."""
    return _get("/api/objects/info", name=name, format="json")


@mcp.tool()
def stellarium_search(term: str) -> list:
    """Himmelsobjekte nach Name suchen. Gibt Liste passender Objekte zurück."""
    result = _get("/api/objects/find", str=term)
    if isinstance(result, list):
        return result
    return []


@mcp.tool()
def stellarium_set_time(date: str) -> str:
    """Simulationszeit setzen. Format: ISO 8601 z.B. '2024-12-21T20:00:00'
    oder Julianisches Datum als String z.B. 'JD2460670.5'."""
    return _post("/api/main/time", {"time": date})


@mcp.tool()
def stellarium_set_timerate(rate: float) -> str:
    """Zeitrafferrate setzen. 1.0 = Echtzeit, 0 = angehalten, -1 = rückwärts,
    3600 = 1 Stunde/Sekunde."""
    return _post("/api/main/time", {"timerate": str(rate)})


@mcp.tool()
def stellarium_set_location(lat: float, lon: float, alt: float = 0, name: str = "") -> str:
    """Beobachterstandort setzen. lat/lon in Dezimalgrad, alt in Metern.
    z.B. lat=52.5, lon=13.4 für Berlin."""
    data = {"latitude": str(lat), "longitude": str(lon), "altitude": str(int(alt))}
    if name:
        data["name"] = name
    return _post("/api/location/setlocationfields", data)


@mcp.tool()
def stellarium_view(az: float | None = None, alt: float | None = None,
                    fov: float | None = None) -> str:
    """Ansicht steuern: Azimut/Höhe in Grad, Sichtfeld (FoV) in Grad.
    Alle Parameter optional — nur gesetzte Werte werden geändert."""
    data = {}
    if az is not None:
        data["az"] = str(az)
    if alt is not None:
        data["alt"] = str(alt)
    if fov is not None:
        data["fov"] = str(fov)
    return _post("/api/main/view", data)


@mcp.tool()
def stellarium_action(action: str) -> str:
    """Stellarium-Aktion ausführen. Bekannte Actions:
    'actionQuit', 'actionSave_Screenshot_Global', 'actionToggle_Atmosphere',
    'actionShow_Constellation_Lines', 'actionShow_Constellation_Labels',
    'actionShow_Constellation_Art', 'actionShow_Grid_Equatorial',
    'actionShow_Grid_Azimuthal', 'actionToggle_GuiHidden'."""
    return _post("/api/stelaction/do", {"id": action})


@mcp.tool()
def stellarium_sky_view() -> dict:
    """Aktuelles Himmelsfeld abrufen (Rektaszension, Deklination, FoV)."""
    return _get("/api/main/view")


@mcp.tool()
def stellarium_planets() -> dict:
    """Positionen aller Planeten im aktuellen Simulationszeitpunkt abrufen."""
    return _get("/api/objects/listobjectsbytype", type="Planet", format="json")


if __name__ == "__main__":
    mcp.run()
