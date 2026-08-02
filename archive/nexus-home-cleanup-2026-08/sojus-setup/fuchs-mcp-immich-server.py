import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-immich",
    instructions="Immich Fotoverwaltung auf darwin26. Fotos suchen, Alben verwalten, Personen und Erinnerungen abrufen.",
)

BASE_URL = os.environ["IMMICH_URL"].rstrip("/") + "/api"
API_KEY  = os.environ["IMMICH_API_KEY"]
HEADERS  = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs):
    resp = httpx.request(method, f"{BASE_URL}{path}", headers=HEADERS, timeout=30, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


def _simplify_asset(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "filename": a.get("originalFileName"),
        "type": a.get("type"),
        "date": a.get("fileCreatedAt"),
        "city": a.get("exifInfo", {}).get("city"),
        "country": a.get("exifInfo", {}).get("country"),
        "make": a.get("exifInfo", {}).get("make"),
        "model": a.get("exifInfo", {}).get("model"),
        "isFavorite": a.get("isFavorite"),
        "isArchived": a.get("isArchived"),
        "thumbUrl": f"{BASE_URL.replace('/api','')}/api/assets/{a.get('id')}/thumbnail",
    }


# ── SUCHE ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def immich_search(query: str, limit: int = 20) -> list:
    """Fotos und Videos per Freitext suchen (CLIP-Suche)."""
    body = {"query": query, "type": "SMART", "size": limit}
    result = api("POST", "/search/smart", json=body)
    assets = result.get("assets", {}).get("items", [])
    return [_simplify_asset(a) for a in assets]

@mcp.tool()
def immich_search_metadata(city: str = "", country: str = "", make: str = "", date_from: str = "", date_to: str = "", limit: int = 20) -> list:
    """Fotos nach Metadaten suchen. date_from/to im Format YYYY-MM-DD."""
    body: dict = {"size": limit, "type": "METADATA"}
    if city:      body["city"] = city
    if country:   body["country"] = country
    if make:      body["make"] = make
    if date_from: body["takenAfter"] = f"{date_from}T00:00:00.000Z"
    if date_to:   body["takenBefore"] = f"{date_to}T23:59:59.999Z"
    result = api("POST", "/search/metadata", json=body)
    assets = result.get("assets", {}).get("items", [])
    return [_simplify_asset(a) for a in assets]

@mcp.tool()
def immich_get_memories() -> list:
    """'Erinnerungen' von heute abrufen (On This Day)."""
    from datetime import date
    today = date.today()
    result = api("GET", "/memories", params={"day": today.day, "month": today.month})
    memories = result if isinstance(result, list) else result.get("memories", [])
    out = []
    for m in memories:
        for a in m.get("assets", [])[:5]:
            item = _simplify_asset(a)
            item["year"] = m.get("data", {}).get("year")
            out.append(item)
    return out


# ── ASSETS ────────────────────────────────────────────────────────────────────

@mcp.tool()
def immich_get_asset(asset_id: str) -> dict:
    """Details zu einem Asset abrufen."""
    return _simplify_asset(api("GET", f"/assets/{asset_id}"))

@mcp.tool()
def immich_get_recent_assets(limit: int = 20) -> list:
    """Neueste Assets abrufen."""
    result = api("GET", "/assets", params={"size": limit, "order": "desc"})
    assets = result if isinstance(result, list) else result.get("assets", [])
    return [_simplify_asset(a) for a in assets[:limit]]

@mcp.tool()
def immich_favorite_asset(asset_id: str, favorite: bool = True) -> dict:
    """Asset als Favorit markieren oder Favorit entfernen."""
    return api("PUT", f"/assets/{asset_id}", json={"isFavorite": favorite})


# ── ALBEN ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def immich_list_albums() -> list:
    """Alle Alben auflisten."""
    albums = api("GET", "/albums")
    return [{"id": a["id"], "name": a["albumName"], "count": a.get("assetCount", 0), "description": a.get("description", "")} for a in albums]

@mcp.tool()
def immich_get_album(album_id: str, limit: int = 50) -> dict:
    """Album-Details und Inhalte abrufen."""
    album = api("GET", f"/albums/{album_id}")
    return {
        "id": album["id"],
        "name": album["albumName"],
        "description": album.get("description", ""),
        "assetCount": album.get("assetCount", 0),
        "assets": [_simplify_asset(a) for a in album.get("assets", [])[:limit]],
    }

@mcp.tool()
def immich_create_album(name: str, description: str = "", asset_ids: list = []) -> dict:
    """Neues Album erstellen. asset_ids = optionale Liste von Asset-IDs."""
    body: dict = {"albumName": name}
    if description: body["description"] = description
    if asset_ids:   body["assetIds"] = asset_ids
    return api("POST", "/albums", json=body)

@mcp.tool()
def immich_add_to_album(album_id: str, asset_ids: list) -> dict:
    """Assets zu einem Album hinzufügen."""
    return api("PUT", f"/albums/{album_id}/assets", json={"ids": asset_ids})


# ── PERSONEN ──────────────────────────────────────────────────────────────────

@mcp.tool()
def immich_list_people() -> list:
    """Alle erkannten Personen auflisten."""
    result = api("GET", "/people")
    people = result.get("people", result) if isinstance(result, dict) else result
    return [{"id": p["id"], "name": p.get("name", ""), "faceCount": p.get("faces", 0)} for p in people]

@mcp.tool()
def immich_get_person_assets(person_id: str, limit: int = 20) -> list:
    """Fotos einer bestimmten Person abrufen."""
    result = api("GET", f"/people/{person_id}/assets")
    assets = result if isinstance(result, list) else result.get("assets", [])
    return [_simplify_asset(a) for a in assets[:limit]]


# ── SERVER-INFO ───────────────────────────────────────────────────────────────

@mcp.tool()
def immich_get_stats() -> dict:
    """Server-Statistiken abrufen (Anzahl Fotos, Videos, Speicher)."""
    return api("GET", "/server/statistics")


if __name__ == "__main__":
    mcp.run()
