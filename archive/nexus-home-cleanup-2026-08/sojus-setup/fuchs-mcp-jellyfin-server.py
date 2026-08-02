import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-jellyfin",
    instructions="Jellyfin Medienserver auf darwin26. Mediathek durchsuchen, Wiedergabe steuern, Bibliothek verwalten.",
)

BASE_URL = os.environ["JELLYFIN_URL"].rstrip("/")
API_KEY  = os.environ["JELLYFIN_API_KEY"]
HEADERS  = {"X-Emby-Token": API_KEY, "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs):
    resp = httpx.request(method, f"{BASE_URL}{path}", headers=HEADERS, timeout=30, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


def _simplify_item(item: dict) -> dict:
    return {
        "Id": item.get("Id"),
        "Name": item.get("Name"),
        "Type": item.get("Type"),
        "Year": item.get("ProductionYear"),
        "Rating": item.get("CommunityRating"),
        "Overview": (item.get("Overview") or "")[:200],
        "RunTimeTicks": item.get("RunTimeTicks"),
        "IsPlayed": item.get("UserData", {}).get("Played"),
        "Path": item.get("Path"),
    }


# ── BIBLIOTHEK ────────────────────────────────────────────────────────────────

@mcp.tool()
def jellyfin_search(query: str, media_type: str = "", limit: int = 20) -> list:
    """Mediathek durchsuchen. media_type: 'Movie', 'Series', 'Episode', 'Audio', 'MusicAlbum'."""
    params = {
        "searchTerm": query,
        "Limit": limit,
        "Recursive": True,
        "Fields": "Overview,Path,CommunityRating,UserData",
    }
    if media_type:
        params["IncludeItemTypes"] = media_type
    result = api("GET", "/Items", params=params)
    return [_simplify_item(i) for i in result.get("Items", [])]

@mcp.tool()
def jellyfin_recently_added(media_type: str = "Movie", limit: int = 10) -> list:
    """Zuletzt hinzugefügte Inhalte abrufen. media_type: 'Movie', 'Series', 'Episode', 'Audio'."""
    params = {
        "Limit": limit,
        "Recursive": True,
        "SortBy": "DateCreated",
        "SortOrder": "Descending",
        "IncludeItemTypes": media_type,
        "Fields": "Overview,CommunityRating,UserData",
    }
    result = api("GET", "/Items", params=params)
    return [_simplify_item(i) for i in result.get("Items", [])]

@mcp.tool()
def jellyfin_continue_watching(limit: int = 10) -> list:
    """'Weiterschauen'-Liste abrufen (angefangene Inhalte)."""
    params = {
        "Limit": limit,
        "Recursive": True,
        "Fields": "Overview,UserData",
        "Filters": "IsResumable",
        "SortBy": "DatePlayed",
        "SortOrder": "Descending",
    }
    result = api("GET", "/Items", params=params)
    return [_simplify_item(i) for i in result.get("Items", [])]

@mcp.tool()
def jellyfin_get_item(item_id: str) -> dict:
    """Details zu einem Medienobjekt abrufen."""
    return _simplify_item(api("GET", f"/Items/{item_id}"))

@mcp.tool()
def jellyfin_list_libraries() -> list:
    """Alle Mediatheken auflisten."""
    result = api("GET", "/Library/VirtualFolders")
    return [{"Id": lib.get("ItemId"), "Name": lib.get("Name"), "Type": lib.get("CollectionType")} for lib in result]

@mcp.tool()
def jellyfin_browse_library(library_id: str, media_type: str = "", limit: int = 30, sort_by: str = "SortName") -> list:
    """Inhalte einer Mediathek abrufen. sort_by: 'SortName', 'DateCreated', 'CommunityRating'."""
    params = {
        "ParentId": library_id,
        "Limit": limit,
        "Recursive": False,
        "SortBy": sort_by,
        "SortOrder": "Ascending",
        "Fields": "Overview,CommunityRating,UserData",
    }
    if media_type:
        params["IncludeItemTypes"] = media_type
    result = api("GET", "/Items", params=params)
    return [_simplify_item(i) for i in result.get("Items", [])]


# ── SESSIONS & WIEDERGABE ─────────────────────────────────────────────────────

@mcp.tool()
def jellyfin_get_sessions() -> list:
    """Aktive Sessions/Clients abrufen (wer schaut gerade was)."""
    sessions = api("GET", "/Sessions")
    return [
        {
            "Id": s.get("Id"),
            "Client": s.get("Client"),
            "DeviceName": s.get("DeviceName"),
            "UserName": s.get("UserName"),
            "NowPlayingItem": s.get("NowPlayingItem", {}).get("Name") if s.get("NowPlayingItem") else None,
            "PlayState": s.get("PlayState", {}).get("IsPaused"),
        }
        for s in sessions
    ]

@mcp.tool()
def jellyfin_play_on_device(session_id: str, item_id: str) -> dict:
    """Medienobjekt auf einem Gerät/Client abspielen."""
    return api("POST", f"/Sessions/{session_id}/Playing", params={"playCommand": "PlayNow", "itemIds": item_id})

@mcp.tool()
def jellyfin_pause_session(session_id: str) -> dict:
    """Wiedergabe pausieren."""
    return api("POST", f"/Sessions/{session_id}/Playing/Unpause")

@mcp.tool()
def jellyfin_stop_session(session_id: str) -> dict:
    """Wiedergabe stoppen."""
    return api("DELETE", f"/Sessions/{session_id}/Playing")


# ── NUTZER ────────────────────────────────────────────────────────────────────

@mcp.tool()
def jellyfin_list_users() -> list:
    """Alle Jellyfin-Nutzer auflisten."""
    users = api("GET", "/Users")
    return [{"Id": u["Id"], "Name": u["Name"], "IsAdmin": u.get("Policy", {}).get("IsAdministrator", False)} for u in users]


if __name__ == "__main__":
    mcp.run()
