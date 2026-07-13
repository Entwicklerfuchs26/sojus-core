#!/usr/bin/env python3
"""
LightBurn MCP Server — Dateioperationen und Projekt-Management für LightBurn.
LightBurn hat keine REST-API; dieser Server bietet dateibasierte Steuerung.
"""

import json
import os
import subprocess
import glob
from fastmcp import FastMCP

mcp = FastMCP("LightBurn")

PREFS_FILE = os.path.expanduser("~/.config/LightBurn/prefs.ini")
DEFAULT_PROJECT_DIRS = [
    os.path.expanduser("~/Dokumente/LightBurn"),
    os.path.expanduser("~/Documents/LightBurn"),
    os.path.expanduser("~/LightBurn"),
    os.path.expanduser("~/Schreibtisch"),
    os.path.expanduser("~/Desktop"),
]


@mcp.tool()
def lightburn_open(file_path: str) -> dict:
    """LightBurn-Projektdatei öffnen (.lbrn2 oder .lbrn).
    Öffnet LightBurn mit der angegebenen Datei."""
    if not os.path.isfile(file_path):
        return {"error": f"Datei nicht gefunden: {file_path}"}
    subprocess.Popen(["lightburn", file_path],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"status": "ok", "opened": file_path}


@mcp.tool()
def lightburn_list_projects(directory: str = "") -> list:
    """LightBurn-Projektdateien (.lbrn2, .lbrn) in einem Verzeichnis auflisten.
    Ohne Angabe werden Standardverzeichnisse durchsucht."""
    results = []
    dirs = [directory] if directory else DEFAULT_PROJECT_DIRS
    for d in dirs:
        if os.path.isdir(d):
            for ext in ("*.lbrn2", "*.lbrn"):
                for f in glob.glob(os.path.join(d, "**", ext), recursive=True):
                    stat = os.stat(f)
                    results.append({
                        "path": f,
                        "name": os.path.basename(f),
                        "size_kb": round(stat.st_size / 1024, 1),
                        "modified": os.path.getmtime(f),
                    })
    results.sort(key=lambda x: x["modified"], reverse=True)
    return results


@mcp.tool()
def lightburn_recent_files() -> list:
    """Zuletzt in LightBurn geöffnete Dateien auflisten."""
    try:
        with open(PREFS_FILE) as f:
            prefs = json.load(f)
        return prefs.get("RecentFiles", [])
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def lightburn_device_info() -> dict:
    """Konfigurierte Laser-Geräte aus LightBurn-Einstellungen lesen."""
    try:
        with open(PREFS_FILE) as f:
            prefs = json.load(f)
        devices = prefs.get("Devices", [])
        return {"devices": devices}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def lightburn_search_projects(query: str, directory: str = "") -> list:
    """LightBurn-Projekte nach Dateiname durchsuchen."""
    all_files = lightburn_list_projects(directory)
    q = query.lower()
    return [f for f in all_files if q in f["name"].lower()]


if __name__ == "__main__":
    mcp.run()
