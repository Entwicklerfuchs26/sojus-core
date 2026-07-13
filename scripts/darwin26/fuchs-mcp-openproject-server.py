import os
import json
import httpx
from fastmcp import FastMCP

mcp = FastMCP("OpenProject MCP – Fuchs")

BASE_URL = os.environ["OPENPROJECT_URL"].rstrip("/")
API_KEY  = os.environ["OPENPROJECT_API_KEY"]
AUTH     = ("apikey", API_KEY)
HEADERS  = {"Content-Type": "application/json", "Accept": "application/json"}


def api(method: str, path: str, **kwargs):
    url  = f"{BASE_URL}/api/v3{path}"
    resp = httpx.request(method, url, auth=AUTH, headers=HEADERS, timeout=30, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


# ── PROJEKTE ──────────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_projects() -> dict:
    """Alle zugänglichen Projekte auflisten."""
    return api("GET", "/projects")

@mcp.tool()
def op_get_project(project_id: str) -> dict:
    """Ein Projekt anhand ID oder Identifier abrufen."""
    return api("GET", f"/projects/{project_id}")

@mcp.tool()
def op_create_project(name: str, identifier: str, description: str = "") -> dict:
    """Neues Projekt erstellen."""
    body: dict = {"name": name, "identifier": identifier}
    if description:
        body["description"] = {"raw": description}
    return api("POST", "/projects", json=body)

@mcp.tool()
def op_update_project(project_id: str, name: str = "", description: str = "") -> dict:
    """Projekt aktualisieren."""
    body: dict = {}
    if name:        body["name"]        = name
    if description: body["description"] = {"raw": description}
    return api("PATCH", f"/projects/{project_id}", json=body)

@mcp.tool()
def op_delete_project(project_id: str) -> dict:
    """Projekt löschen."""
    return api("DELETE", f"/projects/{project_id}")


# ── ARBEITSPAKETE ─────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_work_packages(project_id: str = "", limit: int = 50) -> dict:
    """Arbeitspakete auflisten. Optional für ein bestimmtes Projekt."""
    params = {"pageSize": limit}
    if project_id:
        return api("GET", f"/projects/{project_id}/work_packages", params=params)
    return api("GET", "/work_packages", params=params)

@mcp.tool()
def op_get_work_package(work_package_id: int) -> dict:
    """Ein Arbeitspaket anhand ID abrufen."""
    return api("GET", f"/work_packages/{work_package_id}")

@mcp.tool()
def op_create_work_package(
    project_id: str,
    subject: str,
    type_id: int = 0,
    status_id: int = 0,
    assignee_id: int = 0,
    priority_id: int = 0,
    description: str = "",
    start_date: str = "",
    due_date: str = "",
) -> dict:
    """Arbeitspaket in einem Projekt erstellen."""
    body: dict = {
        "subject": subject,
        "_links": {"project": {"href": f"/api/v3/projects/{project_id}"}},
    }
    if type_id:     body["_links"]["type"]     = {"href": f"/api/v3/types/{type_id}"}
    if status_id:   body["_links"]["status"]   = {"href": f"/api/v3/statuses/{status_id}"}
    if assignee_id: body["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
    if priority_id: body["_links"]["priority"] = {"href": f"/api/v3/priorities/{priority_id}"}
    if description: body["description"] = {"raw": description}
    if start_date:  body["startDate"]   = start_date
    if due_date:    body["dueDate"]     = due_date
    return api("POST", f"/projects/{project_id}/work_packages", json=body)

@mcp.tool()
def op_update_work_package(
    work_package_id: int,
    subject: str = "",
    status_id: int = 0,
    assignee_id: int = 0,
    priority_id: int = 0,
    description: str = "",
    start_date: str = "",
    due_date: str = "",
    done_ratio: int = -1,
) -> dict:
    """Arbeitspaket aktualisieren."""
    current      = api("GET", f"/work_packages/{work_package_id}")
    lock_version = current.get("lockVersion", 0)
    body: dict   = {"lockVersion": lock_version, "_links": {}}
    if subject:           body["subject"]      = subject
    if description:       body["description"]  = {"raw": description}
    if status_id:         body["_links"]["status"]   = {"href": f"/api/v3/statuses/{status_id}"}
    if assignee_id:       body["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
    if priority_id:       body["_links"]["priority"] = {"href": f"/api/v3/priorities/{priority_id}"}
    if start_date:        body["startDate"]    = start_date
    if due_date:          body["dueDate"]      = due_date
    if done_ratio >= 0:   body["percentageDone"] = done_ratio
    return api("PATCH", f"/work_packages/{work_package_id}", json=body)

@mcp.tool()
def op_delete_work_package(work_package_id: int) -> dict:
    """Arbeitspaket löschen."""
    return api("DELETE", f"/work_packages/{work_package_id}")


# ── KOMMENTARE ────────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_work_package_comments(work_package_id: int) -> dict:
    """Kommentare / Aktivitäten eines Arbeitspakets auflisten."""
    return api("GET", f"/work_packages/{work_package_id}/activities")

@mcp.tool()
def op_add_work_package_comment(work_package_id: int, comment: str) -> dict:
    """Kommentar zu einem Arbeitspaket hinzufügen."""
    return api("POST", f"/work_packages/{work_package_id}/activities", json={"comment": {"raw": comment}})


# ── ZEITBUCHUNGEN ─────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_time_entry_activities() -> dict:
    """Verfügbare Zeitbuchungs-Aktivitäten auflisten."""
    return api("GET", "/time_entries/activities")

@mcp.tool()
def op_list_time_entries(project_id: str = "", work_package_id: int = 0, limit: int = 25) -> dict:
    """Zeitbuchungen auflisten, optional gefiltert."""
    filters = []
    if project_id:
        filters.append({"project": {"operator": "=", "values": [project_id]}})
    if work_package_id:
        filters.append({"work_package": {"operator": "=", "values": [str(work_package_id)]}})
    params: dict = {"pageSize": limit}
    if filters:
        params["filters"] = json.dumps(filters)
    return api("GET", "/time_entries", params=params)

@mcp.tool()
def op_create_time_entry(
    work_package_id: int,
    hours: float,
    activity_id: int,
    spent_on: str,
    comment: str = "",
) -> dict:
    """Zeit auf einem Arbeitspaket buchen. spent_on: YYYY-MM-DD."""
    body: dict = {
        "hours": f"PT{hours}H",
        "spentOn": spent_on,
        "_links": {
            "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"},
            "activity":    {"href": f"/api/v3/time_entries/activities/{activity_id}"},
        },
    }
    if comment:
        body["comment"] = {"raw": comment}
    return api("POST", "/time_entries", json=body)

@mcp.tool()
def op_delete_time_entry(time_entry_id: int) -> dict:
    """Zeitbuchung löschen."""
    return api("DELETE", f"/time_entries/{time_entry_id}")


# ── VERSIONEN / MEILENSTEINE ──────────────────────────────────────────────────

@mcp.tool()
def op_list_versions(project_id: str = "") -> dict:
    """Versionen/Meilensteine auflisten."""
    if project_id:
        return api("GET", f"/projects/{project_id}/versions")
    return api("GET", "/versions")

@mcp.tool()
def op_create_version(
    project_id: str, name: str,
    start_date: str = "", due_date: str = "", status: str = "open",
) -> dict:
    """Version/Meilenstein erstellen. status: 'open', 'locked', 'closed'."""
    body: dict = {
        "name": status,
        "status": status,
        "_links": {"definingProject": {"href": f"/api/v3/projects/{project_id}"}},
    }
    body["name"] = name
    if start_date: body["startDate"] = start_date
    if due_date:   body["endDate"]   = due_date
    return api("POST", "/versions", json=body)

@mcp.tool()
def op_update_version(version_id: int, name: str = "", status: str = "", due_date: str = "") -> dict:
    """Version/Meilenstein aktualisieren."""
    body: dict = {}
    if name:     body["name"]    = name
    if status:   body["status"]  = status
    if due_date: body["endDate"] = due_date
    return api("PATCH", f"/versions/{version_id}", json=body)


# ── MITGLIEDSCHAFTEN ──────────────────────────────────────────────────────────

@mcp.tool()
def op_list_memberships(project_id: str = "") -> dict:
    """Mitgliedschaften auflisten, optional pro Projekt."""
    params: dict = {}
    if project_id:
        params["filters"] = json.dumps([{"project": {"operator": "=", "values": [project_id]}}])
    return api("GET", "/memberships", params=params)

@mcp.tool()
def op_create_membership(project_id: str, user_id: int, role_ids: list) -> dict:
    """Nutzer zu Projekt hinzufügen."""
    body = {
        "_links": {
            "project":   {"href": f"/api/v3/projects/{project_id}"},
            "principal": {"href": f"/api/v3/users/{user_id}"},
            "roles":     [{"href": f"/api/v3/roles/{rid}"} for rid in role_ids],
        }
    }
    return api("POST", "/memberships", json=body)

@mcp.tool()
def op_delete_membership(membership_id: int) -> dict:
    """Mitgliedschaft entfernen."""
    return api("DELETE", f"/memberships/{membership_id}")


# ── METADATEN ─────────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_statuses() -> dict:
    """Alle verfügbaren Arbeitspaketstatus auflisten."""
    return api("GET", "/statuses")

@mcp.tool()
def op_list_types(project_id: str = "") -> dict:
    """Arbeitspakettypen auflisten."""
    if project_id:
        return api("GET", f"/projects/{project_id}/types")
    return api("GET", "/types")

@mcp.tool()
def op_list_priorities() -> dict:
    """Alle Prioritäten auflisten."""
    return api("GET", "/priorities")

@mcp.tool()
def op_list_roles() -> dict:
    """Alle verfügbaren Rollen auflisten."""
    return api("GET", "/roles")

@mcp.tool()
def op_list_categories(project_id: str) -> dict:
    """Kategorien eines Projekts auflisten."""
    return api("GET", f"/projects/{project_id}/categories")


# ── NUTZER ────────────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_users() -> dict:
    """Alle Nutzer auflisten."""
    return api("GET", "/users")

@mcp.tool()
def op_get_user(user_id: str) -> dict:
    """Einen Nutzer abrufen. 'me' für den aktuellen Nutzer."""
    return api("GET", f"/users/{user_id}")


# ── NEWS ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def op_list_news(project_id: str = "") -> dict:
    """News auflisten, optional für ein Projekt."""
    if project_id:
        return api("GET", f"/projects/{project_id}/news")
    return api("GET", "/news")


if __name__ == "__main__":
    mcp.run()
