import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-vikunja",
    instructions="Vikunja Task Manager auf tasks.sternenhof.space",
)

BASE_URL = os.environ["VIKUNJA_URL"].rstrip("/") + "/api/v1"
TOKEN = os.environ["VIKUNJA_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs):
    resp = httpx.request(method, f"{BASE_URL}{path}", headers=HEADERS, timeout=30, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


# ── PROJEKTE ──────────────────────────────────────────────────────────────────

@mcp.tool()
def vikunja_list_projects() -> list:
    """Alle Projekte auflisten."""
    return api("GET", "/projects")

@mcp.tool()
def vikunja_get_project(project_id: int) -> dict:
    """Ein Projekt anhand ID abrufen."""
    return api("GET", f"/projects/{project_id}")

@mcp.tool()
def vikunja_create_project(title: str, description: str = "", color: str = "") -> dict:
    """Neues Projekt erstellen."""
    body: dict = {"title": title}
    if description: body["description"] = description
    if color: body["hex_color"] = color
    return api("PUT", "/projects", json=body)

@mcp.tool()
def vikunja_update_project(project_id: int, title: str = "", description: str = "", is_archived: bool = False) -> dict:
    """Projekt aktualisieren."""
    body: dict = {}
    if title: body["title"] = title
    if description: body["description"] = description
    if is_archived: body["is_archived"] = is_archived
    return api("POST", f"/projects/{project_id}", json=body)

@mcp.tool()
def vikunja_delete_project(project_id: int) -> dict:
    """Projekt löschen."""
    return api("DELETE", f"/projects/{project_id}")


# ── TASKS ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def vikunja_list_tasks(project_id: int = 0, page: int = 1, per_page: int = 50) -> list:
    """Tasks auflisten. Ohne project_id alle Tasks, sonst nur die des Projekts."""
    params = {"page": page, "per_page": per_page}
    if project_id:
        return api("GET", f"/projects/{project_id}/tasks", params=params)
    return api("GET", "/tasks/all", params=params)

@mcp.tool()
def vikunja_get_task(task_id: int) -> dict:
    """Einen Task anhand ID abrufen."""
    return api("GET", f"/tasks/{task_id}")

@mcp.tool()
def vikunja_create_task(
    project_id: int,
    title: str,
    description: str = "",
    due_date: str = "",
    priority: int = 0,
) -> dict:
    """Task in einem Projekt erstellen. due_date im ISO-Format (z.B. 2026-07-15T10:00:00Z)."""
    body: dict = {"title": title}
    if description: body["description"] = description
    if due_date:    body["due_date"] = due_date
    if priority:    body["priority"] = priority
    return api("PUT", f"/projects/{project_id}/tasks", json=body)

@mcp.tool()
def vikunja_update_task(
    task_id: int,
    title: str = "",
    description: str = "",
    done: bool = False,
    due_date: str = "",
    priority: int = -1,
) -> dict:
    """Task aktualisieren. done=True markiert als erledigt."""
    body: dict = {}
    if title:        body["title"] = title
    if description:  body["description"] = description
    if done:         body["done"] = done
    if due_date:     body["due_date"] = due_date
    if priority >= 0: body["priority"] = priority
    return api("POST", f"/tasks/{task_id}", json=body)

@mcp.tool()
def vikunja_delete_task(task_id: int) -> dict:
    """Task löschen."""
    return api("DELETE", f"/tasks/{task_id}")

@mcp.tool()
def vikunja_list_task_comments(task_id: int) -> list:
    """Kommentare eines Tasks auflisten."""
    return api("GET", f"/tasks/{task_id}/comments")

@mcp.tool()
def vikunja_create_task_comment(task_id: int, comment: str) -> dict:
    """Kommentar zu einem Task hinzufügen."""
    return api("PUT", f"/tasks/{task_id}/comments", json={"comment": comment})


# ── LABELS ────────────────────────────────────────────────────────────────────

@mcp.tool()
def vikunja_list_labels() -> list:
    """Alle Labels auflisten."""
    return api("GET", "/labels")

@mcp.tool()
def vikunja_create_label(title: str, color: str = "") -> dict:
    """Neues Label erstellen. color als Hex ohne # (z.B. 'ff0000')."""
    body: dict = {"title": title}
    if color: body["hex_color"] = color
    return api("PUT", "/labels", json=body)

@mcp.tool()
def vikunja_add_label_to_task(task_id: int, label_id: int) -> dict:
    """Label zu einem Task hinzufügen."""
    return api("PUT", f"/tasks/{task_id}/labels", json={"label_id": label_id})

@mcp.tool()
def vikunja_remove_label_from_task(task_id: int, label_id: int) -> dict:
    """Label von einem Task entfernen."""
    return api("DELETE", f"/tasks/{task_id}/labels/{label_id}")
