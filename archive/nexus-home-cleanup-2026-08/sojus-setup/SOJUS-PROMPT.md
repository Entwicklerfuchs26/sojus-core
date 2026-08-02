# Sojus – Session-Briefing

Wir bauen **Sojus**, meinen persönlichen KI-Agenten (Jarvis-Style, selbstgehostet, full control).

## Architektur

| Gerät | Rolle |
|---|---|
| **nexus** (Gaming-PC, NixOS + Hyprland) | Claude Code läuft hier |
| **darwin26** (192.168.1.26, NixOS, Mac Mini) | 24/7-Kern: alle Dienste als systemd/NixOS-Module |
| **edaphos** (edaphos.weites-feld.org) | Nextcloud (Username: `entwicklerfuchs`) |
| **wege.weites-feld.org** | OpenProject Community Edition |

SSH auf darwin26: `ssh -i ~/.ssh/darwin26 fuchs@192.168.1.26`  
Sudo auf darwin26: braucht interaktives Terminal (`ssh -t` oder direkt einloggen)  
NixOS-Workflow: Dateien nach `~/sojus-setup/` schreiben → sudo kopieren → `sudo git -C /etc/nixos add ...` → `sudo nixos-rebuild switch --flake /etc/nixos#darwin26`

## Laufende MCP-Server (Claude Code verbunden)

| Name | Port | Dienst | Bemerkung |
|---|---|---|---|
| `nextcloud` | 8000 | Nextcloud (cbcoutinho, 110+ Tools) | User: sojus-mcp |
| `nextcloud-supplement` | 8001 | Eigener FastMCP (Polls, Ankündigungen, Aktivität, Formulare) | User: sojus-mcp-supplement |
| `fuchs-openproject` | 8002 | FastMCP für OpenProject API v3 (28 Tools) | User: fuchs-mcp-openproject |
| `fuchs-vikunja` | 8003 | FastMCP für Vikunja REST-API (Projekte, Tasks, Labels, Kommentare) | JWT-Token, läuft auf localhost:3456 |
| `fuchs-homeassistant` | 8004 | FastMCP für Home Assistant (Entities, Automationen, Szenen, Scripts, iOS-Push) | Long-Lived Token |
| `fuchs-n8n` | 8005 | FastMCP für n8n REST API (Workflows, Executions, Tags) | API-Key aus n8n UI |
| `fuchs-jellyfin` | 8006 | FastMCP für Jellyfin (Suche, Library, Sessions, Playback) | API-Key aus Jellyfin Admin |
| `fuchs-immich` | 8007 | FastMCP für Immich (Suche, Alben, Personen, Erinnerungen) | API-Key aus Immich Account |
| ~~`fuchs-ldap`~~ | ~~8008~~ | ~~OpenLDAP~~ | Nicht gebaut — Web-GUI (ldap-user-manager) vorhanden |

**Naming Convention:** Neue MCP-Services immer mit Präfix `fuchs-` (wegen Multi-User-Zukunft).  
**Env-Dateien:** `/etc/sojus/fuchs-mcp-<name>.env` (root:root, 600)  
**Server-Scripts:** `/etc/sojus/fuchs-mcp-<name>-server.py`  
**NixOS-Module:** `/etc/nixos/sys/darwin26/fuchs-mcp-<name>.nix` + Import in `sys/darwin26/default.nix`

## Nächste Schritte

1. ✅ MCP-Server testen (Kalender, Talk, OpenProject)
2. ✅ mcp-openproject deployed
3. ✅ mcp-vikunja deployed (Port 8003)
4. ✅ mcp-homeassistant deployed (Port 8004)
5. ✅ **iPhone Notify-Target prüfen** — `HA_NOTIFY_TARGET=mobile_app_iphone` korrekt, Notification getestet und angekommen
6. ✅ **fuchs-mcp-n8n** deployed (Port 8005) — n8n API-Key gesetzt, Service aktiv
7. ✅ **fuchs-mcp-jellyfin** deployed (Port 8006) — Jellyfin API-Key gesetzt, Service aktiv
8. ✅ **fuchs-mcp-immich** deployed (Port 8007) — Immich API-Key gesetzt, Service aktiv
9. ⬜ **Claude Code neu starten** — damit n8n, Jellyfin, Immich MCP-Server geladen werden
10. ⬜ **LED-Problem debuggen** — HA schaltet State auf "on" aber physisches Gerät reagiert nicht auf Remote-Befehle
11. ⬜ **n8n Firmenchef** — erster Spezialist-Workflow (Chat + Kalender)
12. ⬜ **Vikunja-Token erneuern** wenn nötig — JWT läuft ~Juli 2027 ab (neu via `POST /api/v1/login`)

## Wichtige Fallstricke

- n8n: Systemfeld wertet keine Expressions aus → Gedächtnis via `{{ $json.memoryText }}`
- MCP Tool-Name-Konflikte crashen den Agenten → umbenennen
- darwin26 NixOS: Dateien müssen `sudo git add`ed sein (Flake sieht nur getrackte Dateien)
- LD_LIBRARY_PATH explizit setzen (stdenv.cc.cc.lib, zlib, openssl, glib) — grpc braucht libstdc++
- nix-ld ist NICHT nötig (LD_LIBRARY_PATH reicht)
- SSH von nexus: `ssh -i ~/.ssh/darwin26 -o IdentitiesOnly=yes fuchs@192.168.1.26` (Key bereits hinterlegt)
- sudo via SSH: immer `-t` Flag verwenden oder direkt auf darwin26 einloggen

## Ziel

Voller Zugriff auf mein digitales Leben: Kalender, Tasks, Chat, Projekte, Dateien, Smart Home.  
Später: Ollama 70B auf Mac Studio M4 als primäres Modell, n8n als Orchestrator.
