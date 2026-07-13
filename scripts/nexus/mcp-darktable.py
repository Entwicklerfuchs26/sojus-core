#!/usr/bin/env python3
"""
Darktable MCP Server
- Bibliothek abfragen (SQLite: library.db + data.db)
- Bilder exportieren via darktable-cli
- Stile, Film-Rollen, Tags, Bewertungen verwalten
"""

import os
import sqlite3
import subprocess
import threading
import time
from contextlib import contextmanager
from fastmcp import FastMCP

mcp = FastMCP("Darktable")

LIBRARY_DB = os.path.expanduser("~/.config/darktable/library.db")
DATA_DB    = os.path.expanduser("~/.config/darktable/data.db")

# Rating in Darktable: flags & 0x7 → 0=unbewertet, 1-5=Sterne, 6=abgelehnt
COLOR_LABELS = {0: "kein", 1: "rot", 2: "gelb", 3: "grün", 4: "blau", 5: "lila"}

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


@contextmanager
def _lib():
    con = sqlite3.connect(LIBRARY_DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


@contextmanager
def _data():
    con = sqlite3.connect(DATA_DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def _img_to_dict(row) -> dict:
    d = dict(row)
    d["rating"] = d.get("flags", 0) & 0x7
    d["rejected"] = d["rating"] == 6
    return d


@mcp.tool()
def darktable_list_film_rolls() -> list:
    """Alle Film-Rollen (importierten Ordner) auflisten mit Anzahl Bilder."""
    with _lib() as con:
        rows = con.execute("""
            SELECT f.id, f.folder,
                   COUNT(i.id) as count,
                   MIN(i.datetime_taken) as earliest,
                   MAX(i.datetime_taken) as latest
            FROM film_rolls f
            LEFT JOIN images i ON i.film_id = f.id
            GROUP BY f.id
            ORDER BY f.id DESC
        """).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def darktable_search_images(
    query: str = "",
    film_roll_id: int = 0,
    min_rating: int = 0,
    color_label: str = "",
    limit: int = 50,
) -> list:
    """Bilder in der Darktable-Bibliothek suchen.
    query: Suche im Dateinamen.
    film_roll_id: auf eine Film-Rolle einschränken (0 = alle).
    min_rating: Mindestbewertung 1-5 (0 = alle).
    color_label: 'rot', 'gelb', 'grün', 'blau', 'lila' oder leer für alle.
    limit: max. Ergebnisse (default 50)."""
    conditions = []
    params: list = []

    if query:
        conditions.append("i.filename LIKE ?")
        params.append(f"%{query}%")
    if film_roll_id:
        conditions.append("i.film_id = ?")
        params.append(film_roll_id)
    if min_rating > 0:
        conditions.append("(i.flags & 7) >= ?")
        params.append(min_rating)

    color_id = next((k for k, v in COLOR_LABELS.items() if v == color_label), None)
    label_join = ""
    if color_id is not None and color_id > 0:
        label_join = "JOIN color_labels cl ON cl.imgid = i.id AND cl.color = ?"
        params.insert(0, color_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT i.id, f.folder, i.filename, i.datetime_taken,
               i.width, i.height, i.aperture, i.exposure, i.iso,
               i.focal_length, i.maker_id, i.model_id,
               (i.flags & 7) as rating
        FROM images i
        JOIN film_rolls f ON f.id = i.film_id
        {label_join}
        {where}
        ORDER BY i.datetime_taken DESC
        LIMIT ?
    """
    params.append(limit)

    with _lib() as con:
        rows = con.execute(sql, params).fetchall()

    return [
        {**dict(r), "path": os.path.join(r["folder"], r["filename"])}
        for r in rows
    ]


@mcp.tool()
def darktable_image_info(image_id: int) -> dict:
    """Vollständige Metadaten eines Bildes abrufen (EXIF, Bearbeitungshistorie, Tags)."""
    with _lib() as con:
        img = con.execute("""
            SELECT i.*, f.folder,
                   mk.name as maker, mo.name as model, l.name as lens
            FROM images i
            JOIN film_rolls f ON f.id = i.film_id
            LEFT JOIN makers mk ON mk.id = i.maker_id
            LEFT JOIN models mo ON mo.id = i.model_id
            LEFT JOIN lens l ON l.id = i.lens_id
            WHERE i.id = ?
        """, (image_id,)).fetchone()
        if not img:
            return {"error": f"Bild {image_id} nicht gefunden"}

        tags = con.execute("""
            SELECT t.name FROM tagged_images ti
            JOIN tags t ON t.id = ti.tagid WHERE ti.imgid = ?
        """, (image_id,)).fetchall()

        labels = con.execute(
            "SELECT color FROM color_labels WHERE imgid = ?", (image_id,)
        ).fetchall()

        history_count = con.execute(
            "SELECT COUNT(*) FROM history WHERE imgid = ?", (image_id,)
        ).fetchone()[0]

    result = dict(img)
    result["path"] = os.path.join(img["folder"], img["filename"])
    result["rating"] = result.get("flags", 0) & 0x7
    result["tags"] = [r["name"] for r in tags]
    result["color_labels"] = [COLOR_LABELS.get(r["color"], "?") for r in labels]
    result["history_steps"] = history_count
    return result


@mcp.tool()
def darktable_list_styles(filter: str = "") -> list:
    """Verfügbare Darktable-Stile auflisten. filter: Textsuche im Style-Namen."""
    with _data() as con:
        rows = con.execute(
            "SELECT name, description FROM styles ORDER BY name"
        ).fetchall()
    styles = [dict(r) for r in rows]
    if filter:
        f = filter.lower()
        styles = [s for s in styles if f in s["name"].lower() or f in (s["description"] or "").lower()]
    # Kamera-Stile ausblenden wenn kein Filter (sehr lang)
    if not filter:
        styles = [s for s in styles if not s["name"].startswith("_l10n_darktable|_l10n_camera")]
    return styles


@mcp.tool()
def darktable_export(
    image_path: str,
    output_dir: str,
    style: str = "",
    width: int = 0,
    height: int = 0,
    format: str = "jpg",
) -> dict:
    """Ein Bild mit darktable-cli exportieren.
    image_path: Pfad zur RAW/Bilddatei.
    output_dir: Ausgabeverzeichnis (wird erstellt falls nötig).
    style: optionaler Darktable-Stil (Name aus darktable_list_styles).
    width/height: max. Ausgabegröße (0 = volle Auflösung).
    format: 'jpg', 'png', 'tif', 'webp'."""
    if not os.path.isfile(image_path):
        return {"error": f"Datei nicht gefunden: {image_path}"}
    os.makedirs(output_dir, exist_ok=True)

    cmd = ["darktable-cli", image_path, output_dir,
           "--out-ext", format, "--hq", "true"]
    if style:
        cmd += ["--style", style]
    if width:
        cmd += ["--width", str(width)]
    if height:
        cmd += ["--height", str(height)]

    job_id = f"dt_{int(time.time())}"
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running", "input": image_path,
            "output_dir": output_dir, "format": format, "style": style,
        }

    def _run():
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        with _jobs_lock:
            _jobs[job_id]["status"] = "done" if result.returncode == 0 else "error"
            _jobs[job_id]["returncode"] = result.returncode
            _jobs[job_id]["stderr"] = result.stderr[-2000:]

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id, "status": "gestartet", "cmd": " ".join(cmd)}


@mcp.tool()
def darktable_export_status(job_id: str) -> dict:
    """Status eines laufenden oder abgeschlossenen Export-Jobs abrufen."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    return job or {"error": f"Job nicht gefunden: {job_id}"}


@mcp.tool()
def darktable_stats() -> dict:
    """Bibliotheksstatistiken: Gesamtzahl Bilder, Bewertungsverteilung, Kameras."""
    with _lib() as con:
        total = con.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        by_rating = con.execute("""
            SELECT (flags & 7) as rating, COUNT(*) as count
            FROM images GROUP BY rating ORDER BY rating
        """).fetchall()
        cameras = con.execute("""
            SELECT mo.name as model, mk.name as maker, COUNT(i.id) as count
            FROM images i
            LEFT JOIN models mo ON mo.id = i.model_id
            LEFT JOIN makers mk ON mk.id = i.maker_id
            GROUP BY i.model_id ORDER BY count DESC LIMIT 10
        """).fetchall()
    return {
        "total_images": total,
        "by_rating": {str(r["rating"]): r["count"] for r in by_rating},
        "cameras": [dict(c) for c in cameras],
    }


if __name__ == "__main__":
    mcp.run()
