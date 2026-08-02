import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-n8n",
    instructions="n8n Workflow-Automation auf darwin26. Workflows triggern, verwalten und erstellen.",
)

BASE_URL = os.environ["N8N_URL"].rstrip("/") + "/api/v1"
API_KEY  = os.environ["N8N_API_KEY"]
HEADERS  = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs):
    resp = httpx.request(method, f"{BASE_URL}{path}", headers=HEADERS, timeout=30, **kwargs)
    resp.raise_for_status()
    if resp.status_code == 204:
        return {"success": True}
    return resp.json()


# ── WORKFLOWS ─────────────────────────────────────────────────────────────────

@mcp.tool()
def n8n_list_workflows(active_only: bool = False) -> list:
    """Alle Workflows auflisten (id, name, active-Status)."""
    params = {}
    if active_only:
        params["active"] = "true"
    result = api("GET", "/workflows", params=params)
    workflows = result.get("data", result) if isinstance(result, dict) else result
    return [{"id": w["id"], "name": w["name"], "active": w.get("active", False)} for w in workflows]

@mcp.tool()
def n8n_get_workflow(workflow_id: str) -> dict:
    """Einen Workflow mit allen Nodes und Verbindungen abrufen."""
    return api("GET", f"/workflows/{workflow_id}")

@mcp.tool()
def n8n_create_workflow(name: str, nodes: list, connections: dict, settings: dict = {}) -> dict:
    """Neuen Workflow erstellen. nodes = Liste von Node-Objekten, connections = Verbindungs-Dict.

    Jeder Node braucht: id, name, type, position ([x,y]), parameters.
    Beispiel-Node: {"id":"1","name":"Start","type":"n8n-nodes-base.manualTrigger","position":[250,300],"parameters":{}}
    """
    body = {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": settings or {"executionOrder": "v1"},
    }
    return api("POST", "/workflows", json=body)

@mcp.tool()
def n8n_update_workflow(workflow_id: str, name: str = "", nodes: list = [], connections: dict = {}) -> dict:
    """Workflow aktualisieren (Name, Nodes oder Verbindungen ändern)."""
    current = api("GET", f"/workflows/{workflow_id}")
    body = {
        "name": name or current["name"],
        "nodes": nodes or current["nodes"],
        "connections": connections or current["connections"],
        "settings": current.get("settings", {}),
    }
    return api("PATCH", f"/workflows/{workflow_id}", json=body)

@mcp.tool()
def n8n_delete_workflow(workflow_id: str) -> dict:
    """Workflow löschen."""
    return api("DELETE", f"/workflows/{workflow_id}")

@mcp.tool()
def n8n_activate_workflow(workflow_id: str) -> dict:
    """Workflow aktivieren (startet Trigger wie Cron, Webhook)."""
    return api("POST", f"/workflows/{workflow_id}/activate")

@mcp.tool()
def n8n_deactivate_workflow(workflow_id: str) -> dict:
    """Workflow deaktivieren."""
    return api("POST", f"/workflows/{workflow_id}/deactivate")


# ── AUSFÜHRUNGEN ──────────────────────────────────────────────────────────────

@mcp.tool()
def n8n_list_executions(workflow_id: str = "", limit: int = 20, status: str = "") -> list:
    """Ausführungen auflisten. status: 'success', 'error', 'waiting'."""
    params: dict = {"limit": limit}
    if workflow_id:
        params["workflowId"] = workflow_id
    if status:
        params["status"] = status
    result = api("GET", "/executions", params=params)
    executions = result.get("data", result) if isinstance(result, dict) else result
    return [
        {
            "id": e["id"],
            "workflowId": e.get("workflowId"),
            "status": e.get("status"),
            "startedAt": e.get("startedAt"),
            "stoppedAt": e.get("stoppedAt"),
        }
        for e in executions
    ]

@mcp.tool()
def n8n_get_execution(execution_id: str) -> dict:
    """Details einer Ausführung abrufen (inkl. Daten und Fehler)."""
    return api("GET", f"/executions/{execution_id}")

@mcp.tool()
def n8n_run_workflow(workflow_id: str, data: dict = {}) -> dict:
    """Workflow manuell ausführen (nur für Workflows mit Manual-Trigger).
    data = optionale Eingabedaten."""
    body: dict = {}
    if data:
        body["data"] = data
    return api("POST", f"/workflows/{workflow_id}/run", json=body)


# ── CREDENTIALS & TAGS ────────────────────────────────────────────────────────

@mcp.tool()
def n8n_list_tags() -> list:
    """Alle Tags auflisten."""
    result = api("GET", "/tags")
    tags = result.get("data", result) if isinstance(result, dict) else result
    return tags

@mcp.tool()
def n8n_get_workflow_tags(workflow_id: str) -> list:
    """Tags eines Workflows abrufen."""
    return api("GET", f"/workflows/{workflow_id}/tags")


if __name__ == "__main__":
    mcp.run()
