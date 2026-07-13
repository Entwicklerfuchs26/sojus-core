#!/usr/bin/env python3
"""
HandBrake MCP Server — wraps HandBrakeCLI for video encoding.
Kein GUI nötig, arbeitet rein mit der CLI.
"""

import json
import os
import subprocess
import threading
import time
from fastmcp import FastMCP

mcp = FastMCP("HandBrake")

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _run_encode(job_id: str, cmd: list[str], output_file: str) -> None:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log_lines = []
    progress = 0.0
    for line in proc.stdout:
        log_lines.append(line.rstrip())
        if "Encoding:" in line and "%" in line:
            try:
                pct = line.split("%")[0].rsplit(" ", 1)[-1]
                progress = float(pct)
            except ValueError:
                pass
        with _jobs_lock:
            _jobs[job_id]["progress"] = progress
            _jobs[job_id]["last_line"] = line.rstrip()
    proc.wait()
    with _jobs_lock:
        _jobs[job_id]["status"] = "done" if proc.returncode == 0 else "error"
        _jobs[job_id]["returncode"] = proc.returncode
        _jobs[job_id]["progress"] = 100.0 if proc.returncode == 0 else progress
        _jobs[job_id]["output_file"] = output_file
        _jobs[job_id]["log_tail"] = log_lines[-20:]


@mcp.tool()
def handbrake_encode(
    input_file: str,
    output_file: str,
    preset: str = "Fast 1080p30",
    extra_args: str = "",
) -> dict:
    """Video enkodieren mit HandBrake. Startet Job im Hintergrund.
    preset: z.B. 'Fast 1080p30', 'Fast 2160p60 4K HEVC', 'Very Fast 720p30'.
    extra_args: optionale zusätzliche HandBrakeCLI-Argumente als String.
    Gibt job_id zurück — Status mit handbrake_job_status prüfen."""
    if not os.path.isfile(input_file):
        return {"error": f"Eingabedatei nicht gefunden: {input_file}"}
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        return {"error": f"Ausgabeverzeichnis existiert nicht: {output_dir}"}
    cmd = ["HandBrakeCLI", "--input", input_file, "--output", output_file,
           "--preset", preset]
    if extra_args:
        cmd += extra_args.split()
    job_id = f"hb_{int(time.time())}"
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running", "progress": 0.0, "last_line": "",
            "input": input_file, "output": output_file, "preset": preset,
            "started": time.strftime("%H:%M:%S"),
        }
    t = threading.Thread(target=_run_encode, args=(job_id, cmd, output_file), daemon=True)
    t.start()
    return {"job_id": job_id, "status": "gestartet", "output_file": output_file}


@mcp.tool()
def handbrake_job_status(job_id: str) -> dict:
    """Status eines laufenden oder abgeschlossenen Encode-Jobs abrufen."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return {"error": f"Job nicht gefunden: {job_id}"}
    return job


@mcp.tool()
def handbrake_list_jobs() -> list:
    """Alle aktiven und abgeschlossenen Encode-Jobs auflisten."""
    with _jobs_lock:
        return [
            {"job_id": jid, "status": j["status"], "progress": j["progress"],
             "input": j["input"], "output": j["output"], "preset": j["preset"]}
            for jid, j in _jobs.items()
        ]


@mcp.tool()
def handbrake_scan(input_file: str) -> str:
    """Eingabedatei scannen: zeigt Titel, Kapitel, Video-/Audiospuren, Auflösung.
    Nützlich um verfügbare Spuren und Kapitel zu sehen bevor man enkodiert."""
    if not os.path.isfile(input_file):
        return f"Datei nicht gefunden: {input_file}"
    result = subprocess.run(
        ["HandBrakeCLI", "--scan", "--input", input_file],
        capture_output=True, text=True, timeout=60
    )
    output = result.stderr or result.stdout
    # Nur relevante Zeilen
    lines = [l for l in output.split("\n") if any(
        x in l for x in ["+ title", "+ duration", "+ size", "fps", "audio", "subtitle",
                          "chapters", "stream", "pixel", "display", "+ angle"]
    )]
    return "\n".join(lines) if lines else output[:3000]


@mcp.tool()
def handbrake_list_presets() -> str:
    """Alle verfügbaren HandBrake-Presets auflisten (Kategorien und Namen)."""
    result = subprocess.run(
        ["HandBrakeCLI", "--preset-list"],
        capture_output=True, text=True, timeout=15
    )
    output = result.stdout + result.stderr
    lines = [l for l in output.split("\n") if not l.startswith("[") and l.strip()]
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
