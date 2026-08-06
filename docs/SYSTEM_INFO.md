# SYSTEM_INFO — Sojus-Infrastruktur

Stand: 2026-08-03. Quelle: sojus-core-Repo (`/home/fuchs/sojus-core`) +
`/etc/nixos/nixos-config` (nexus) + Live-Checks auf beiden Hosts. Enthält
keine echten Secret-Werte — nur Fundorte und Verwendungszweck.

---

## [HARDWARE]

**nexus** — IP 192.168.1.40
- CPU: AMD Ryzen 7 3700X (8 Kerne / 16 Threads)
- GPU: NVIDIA GeForce RTX 2070 SUPER, 8192 MiB VRAM
- RAM: ~31 GiB
- Rolle: Jonas' Hauptworkstation (Hyprland-Desktop, Gaming, KI-Tooling). Läuft
  hier auch Claude Code/Sojus (dieser Agent, User `fuchs`) sowie 13 der 25
  MCP-Server (12 App-MCP-Server + fuchs-shell).

**darwin26** — IP 192.168.1.26
- CPU: Intel Core i7-3720QM @ 2.60GHz (4 Kerne / 8 Threads)
- RAM: ~15 GiB
- Rolle: Home-Server. Hostet Nextcloud/Sternenhof-Dienste (*.sternenhof.space),
  Hermes Agent (Port 3002), Open WebUI, mcp-approval-service und 12 der 25
  MCP-Server.

**Mac Studio M4, 64GB** — bestellt, noch nicht live (Stand laut Jonas).

---

## [NETZWERK]

**Kein WireGuard/VPN gefunden.** Weder in `sojus-core` noch in
`/etc/nixos/nixos-config` existiert eine WireGuard-Konfiguration — die
Absicherung läuft ausschließlich über LAN-Segmentierung (192.168.1.0/24) +
iptables + Bearer-Token. Falls WireGuard geplant war: nicht implementiert,
oder an anderer Stelle dokumentiert, die hier nicht geprüft wurde.

**Firewall nexus** (`sojus-core/nexus/default.nix`): dedizierte iptables-Chain
`mcp-sojus-filter` vor Port 9000-9011 (12 App-MCP-Server) und 8012
(fuchs-shell). Nur zwei Quell-IPs dürfen durch:
- `192.168.1.26` (darwin26)
- `192.168.1.40` (nexus selbst)

Alles andere wird verworfen + geloggt (`nixos-fw-log-refuse`). Zusätzlich
offen (unabhängig von MCP, aus `hosts/nexus/host-config.nix`):
TCP 8080, 8081, 8888, 7777.

**Firewall darwin26**: **kein** IP-Filter-Chain wie bei nexus — Schutz läuft
stattdessen über Bearer-Token (`hermesApiKey` für Hermes/3002,
`approvalApiToken` für mcp-approval-service/8014 und den Approval-Proxy).
Offene Ports über `networking.firewall.allowedTCPPorts`: 8000-8009, 8011,
8013, 8014, 3002 — LAN-weit erreichbar, nicht auf bestimmte Quell-IPs
beschränkt.

**Zusammenfassung Erreichbarkeit:**
| Host | Ports | Wer darf zugreifen |
|---|---|---|
| nexus | 9000-9011, 8012 | nur 192.168.1.26 + 192.168.1.40 |
| darwin26 | 8000-8009, 8011, 8013, 8014, 3002 | ganzes LAN, Auth via Bearer-Token |

---

## [MCP_SERVER]

Tier-Klassifizierung folgt einer generischen Verb-Engine
(`scripts/shared/mcp_risk_classifier.py`) + Overrides in
`config/tool_tiers.json`: Tier 3 = {delete, remove, purge, destroy, trash,
wipe, erase, drop}, Tier 2 = {create, update, write, send, post, set, add, …},
Tier 1 = alles andere (get, list, search, read, …). "Gemischt" unten heißt:
Tier hängt vom jeweils aufgerufenen Tool-Namen ab.

**Nextcloud-Disambiguierung (Korrektur ggü. Annahme):** Es gibt **keinen**
literalen `sh__`/`wf__`-Tool-Präfix. Beide Nextcloud-Instanzen exponieren
identische `nc_*`-Tool-Namen; unterschieden wird ausschließlich über den
**Servernamen**:
- `nc-weites-feld` / `nc-weites-feld-extra` = wf = edaphos.weites-feld.org
- `nc-sternenhof` = sh = cloud.sternenhof.space (privat)

### darwin26 (127.0.0.1) — hinter mcp-approval-proxy, außer wo vermerkt

| Server | Port | Beschreibung | Tier | Besonderheit |
|---|---|---|---|---|
| nc-weites-feld | 8000 | Nextcloud @ edaphos.weites-feld.org (Kalender/WebDAV/Notes/Cookbook/News/Tables) | gemischt | hinter Proxy |
| nc-weites-feld-extra | 8001 | Nextcloud Supplement (Aktivität, Ankündigungen, Polls, Formulare) | gemischt | hinter Proxy |
| fuchs-openproject | 8002 | OpenProject Projektmanagement | gemischt | hinter Proxy |
| fuchs-vikunja | 8003 | Vikunja Task Manager | gemischt | hinter Proxy |
| fuchs-homeassistant | 8004 | Home Assistant (Entities, Automationen, Push) | gemischt | `ha_restart`=Tier3-, `ha_call_service`=Tier2-Override; hinter Proxy |
| fuchs-n8n | 8005 | n8n Workflow-Automation | gemischt | hinter Proxy |
| fuchs-jellyfin | 8006 | Jellyfin Mediaserver | gemischt | hinter Proxy |
| fuchs-immich | 8007 | Immich Fotoverwaltung | gemischt | hinter Proxy |
| fuchs-anilist | 8008 | AniList Anime/Manga | gemischt | Pilot-Server für Phase-2-Proxy; hinter Proxy |
| nc-sternenhof | 8009 | Nextcloud @ cloud.sternenhof.space (privat) | gemischt | hinter Proxy |
| fuchs-discord | 8011 | Discord Bot + MCP | gemischt | **nicht** hinter approval-proxy |
| fuchs-email | 8013 | E-Mail MCP (Hofpause/Arteigen-Postfächer) | gemischt | **nicht** hinter approval-proxy |

### nexus (192.168.1.40) — hinter eigenem Approval-Proxy, außer fuchs-shell

| Server | Port | Beschreibung | Tier | Besonderheit |
|---|---|---|---|---|
| fuchs-filesystem | 9000 | Dateisystem-Zugriff (mcp-proxy stdio→HTTP via npx) | gemischt | bekannter Bug: crash-loop (`ImportError request_ctx`, mcp-proxy-Versionsdrift, noch offen) |
| fuchs-hyprland | 9001 | Hyprland WM-Steuerung | gemischt | nur wenn Hyprland läuft |
| fuchs-vivaldi | 9002 | Vivaldi Browser (CDP) | gemischt | nur wenn Vivaldi + CDP Port 9222 läuft |
| fuchs-obs | 9003 | OBS Studio (mcp-proxy → npx) | gemischt | bekannter Bug: crash-loop |
| fuchs-libreoffice | 9004 | LibreOffice Writer | gemischt | nur wenn LibreOffice + MCP-Server (Port 8765) läuft |
| fuchs-freecad | 9005 | FreeCAD CAD (mcp-proxy → uvx) | gemischt | bekannter Bug: crash-loop |
| fuchs-davinci | 9006 | DaVinci Resolve (mcp-proxy → uvx) | gemischt | bekannter Bug: crash-loop |
| fuchs-blender | 9007 | Blender 3D (mcp-proxy → uvx) | gemischt | bekannter Bug: crash-loop |
| fuchs-stellarium | 9008 | Stellarium Planetarium | gemischt | nur wenn Stellarium + RemoteControl-Plugin läuft |
| fuchs-handbrake | 9009 | HandBrake Video-Encode | gemischt | kein GUI nötig |
| fuchs-lightburn | 9010 | LightBurn Laser-CAD | gemischt | Öffnen braucht laufendes LightBurn |
| fuchs-darktable | 9011 | Darktable Fotografie | gemischt | kein GUI nötig (SQLite direkt) |
| fuchs-shell | 8012 | Shell-Zugriff als User `sojus` | gemischt, `execute_command`=content-based | **eigenes Tier-Gate direkt im Server** (kein Proxy davor — Doppel-Gating vermieden); Tier-3 wartet bis 90s auf Freigabe via mcp-approval-service, fail-closed wenn Service nicht erreichbar |

25 Server insgesamt (12 darwin26 + 13 nexus). Bekannte Lücke:
`fuchs-mcp-nextcloud-private` hat kein `SSL_CERT_FILE` für das
cloud.sternenhof.space-Zertifikat → `nc_calendar_*` schlägt dort mit
SSL-Fehler fehl (vorbestehend).

---

## [NIXOS_MODULE]

### darwin26 (`sojus-core/darwin26/*.nix`)
- `default.nix` — importiert alle Module unten
- `secrets.nix` — sops-nix Secret-Definitionen, siehe [SECRETS]
- `tools.nix` — installiert `sops`, `age`, `ssh-to-age` systemweit
- `hermes.nix` — Hermes-Agent-Service (Port 3002): SOUL.md + config.yaml-Deploy via ExecStartPre, MCP-Server-Liste, `platform_toolsets.api_server`
- `mcp-approval-service.nix` — zentrale Freigabe-Warteschlange (Port 8014), SQLite unter `/var/lib/mcp-approval/approvals.db`, TTL 300s, kein IP-Filter (Bearer-Token-Schutz)
- `mcp-approval-proxy.nix` — Tier-Gate-Proxy vor 10 der 12 darwin26-MCP-Server (nicht discord/email)
- `open-webui.nix` — Open WebUI Frontend, zeigt auf Hermes
- `fuchs-discord.nix`, `fuchs-email.nix` — eigene MCP-Server, nicht hinter approval-proxy
- `mcp-nextcloud.nix` (nc-weites-feld), `mcp-supplement.nix` (nc-weites-feld-extra), `mcp-openproject.nix`, `fuchs-mcp-vikunja.nix`, `fuchs-mcp-homeassistant.nix`, `fuchs-mcp-n8n.nix`, `fuchs-mcp-jellyfin.nix`, `fuchs-mcp-immich.nix`, `fuchs-mcp-anilist.nix`, `fuchs-mcp-nextcloud-private.nix` (nc-sternenhof) — je ein MCP-Server-Modul

### nexus (`sojus-core/nexus/*.nix`)
- `default.nix` — importiert alle 12 App-MCP-Module + fuchs-shell + approval-proxy, definiert Firewall-Chain `mcp-sojus-filter`
- `fuchs-shell.nix` — Shell-MCP mit eigenem Tier-Gate, User `sojus`
- `mcp-approval-proxy.nix` — Tier-Gate-Proxy vor den 12 App-MCP-Servern (nicht fuchs-shell)
- `fuchs-mcp-{filesystem,hyprland,vivaldi,obs,libreoffice,freecad,davinci,blender,stellarium,handbrake,lightburn,darktable}.nix` — je ein MCP-Server-Modul, teils mcp-proxy stdio→HTTP-Brücke (npx/uvx)

### Zusätzlich, direkt in `/etc/nixos/nixos-config` (nicht sojus-core)
- `modules/ai/sojus.nix` — `sojus`-User-Definition, NOPASSWD-Sudoers-Whitelist für sojus (nixos-rebuild build/build-vm/switch, systemctl restart/status sojus-core + fuchs-shell, `safe-rebuild.sh`), deployt `safe-rebuild.sh` (Pre-/Post-Rebuild Git-Commit + Pflicht-`build-vm`-Testbuild vor jedem `switch`)
- `hosts/nexus/host-config.nix` — Hostname, SSSD/LDAP-Konfig gegen darwin26, `/etc/hosts`-Einträge für alle `*.sternenhof.space`-Subdomains, Firewall `allowedTCPPorts [8080 8081 8888 7777]`, Hauptbenutzer `fuchs`

---

## [SICHERHEIT]

**Tier-Modell (echtes Verhalten, siehe `scripts/nexus/fuchs-shell-server.py` +
`scripts/shared/mcp_risk_classifier.py`) — Korrektur ggü. ursprünglicher
Annahme "Tier 2 = eine Bestätigung, Tier 3 = zwei Bestätigungen + Code":**
Es gibt nur zwei tatsächliche Zustände.
- **Tier 1** (lesend: get/list/search/find/read/…) → läuft sofort.
- **Tier 2** (schreibend: create/update/write/send/set/add/…) → läuft
  **ebenfalls sofort**, wird aber mit WARNING-Level geloggt. Keine Bestätigung.
- **Tier 3** (destruktiv/systemkritisch) → `execute_command` hält an und
  wartet synchron bis zu 90s (Poll alle 3s) auf **eine** Freigabe durch Jonas
  über `mcp-approval-service` (REST-API, optional HA-Push). Kein Zwei-Schritt-
  Token/Code-Verfahren mehr — das gab es in einer früheren Version, wurde aber
  durch den Approval-Service ersetzt. Fail-closed: Service nicht konfiguriert
  oder nicht erreichbar → Ablehnung, nie Ausführung.

**Hard-Blacklist** (greift unabhängig von Tier, `mcp_risk_classifier.HARD_BLOCK_RE`):
`rm -rf /`, `dd if=/dev/(zero|random) of=/dev/...`, `mkfs.*`, Fork-Bomb-Muster
(`:(){ :|:& };:`), `kill -9 -1`, Pipe in Shell (`| sh`/`| bash`/`| zsh`),
`bash <(curl ...)`, `wget -O- ... | sh`.

**Tier-3-Muster für `execute_command`** (content-based, nicht nur Tool-Name):
`poweroff`, `shutdown`, `reboot`, `nixos-rebuild`, `systemctl
stop/restart/disable/mask`, `rm -rf`, `mkfs`, `dd if=`, SQL `DROP
TABLE`/`TRUNCATE`/`DELETE FROM`, `chmod -R 000/777`, `chown -R root`,
Redirect nach `/etc/`, `pkill -9`/`kill -9`, `docker stop/kill/restart`,
Redirect nach `/dev/sd*`, sowie jede Befehlsverkettung (`&&`, `||`, `;`).

**Bekannte Lücke:** `fuchs-discord` (8011) und `fuchs-email` (8013) auf
darwin26 laufen **nicht** hinter dem mcp-approval-proxy — kein Tier-Gate für
diese beiden Server.

**ACL-Rechte `sojus`-User auf nexus** (Stand 2026-08-03, gesetzt via `setfacl`,
nicht rekursiv über Nix-Rebuild verwaltet — muss nach Neuanlage von Dateien
ggf. erneuert werden, Default-ACL deckt aber Neuanlagen unter bestehenden
Verzeichnissen automatisch ab):
- `/etc/nixos` — rekursiv `r-x` (lesen+listen), inkl. Default-ACL
- `/home/fuchs` — rekursiv `r-x`, Mask korrigiert auf `r-x` (vorher durch
  `mask::---` neutralisiert), inkl. Default-ACL. Enthält Jonas' komplette
  Userdaten (SSH-Keys, Projekte, Downloads, `.claude`-Verlauf etc.) — bewusst
  weitreichender Zugriff für Systemintrospektion.
- `/var/log` — **nicht gesetzt**, root-Verzeichnis, sudo mit Passwort nötig, kein NOPASSWD-Pfad für `fuchs`. Offen, siehe Notiz am Ende dieses Dokuments.
- Verifiziert: `sojus` kann `/etc/nixos/nixos-config/flake.nix` lesen,
  Schreibversuch schlägt mit `Permission denied` fehl.
- Ein kleiner Teil der Dateien unter `/etc/nixos` und `/home/fuchs` gehört
  root oder anderen UIDs (Docker-Build-Artefakte, `__pycache__`,
  vereinzelte `.git/objects`) — dort griff `setfacl` nicht (Eigentümer-Check),
  betrifft aber nur schon anderweitig world-readable Dateien oder unkritische
  Cache-Reste.
- `sojus` hat zusätzlich eigene NOPASSWD-Sudoers-Regeln (unabhängig von ACL,
  siehe `modules/ai/sojus.nix`): `nixos-rebuild build/build-vm/switch`,
  `systemctl restart/status sojus-core`, `systemctl restart/status
  fuchs-shell`, `safe-rebuild.sh`. Explizit **nicht** erlaubt: `dd`, `mkfs`,
  `parted`, `userdel`, `passwd` für andere User, `rm -rf` auf Systempfade,
  `shutdown`, `poweroff`.

---

## [SECRETS]

**Korrektur ggü. ursprünglicher Annahme** ("agenix auf darwin26, sops auf
nexus") — es ist genau umgekehrt:

- **nexus nutzt agenix.** Liegt in `/etc/nixos/secrets/` (lokale
  nixos-config, Recipient-Key `ssh-ed25519 ...root@nexus`) sowie
  `sojus-core/secrets/secrets.nix`. Bekannte `.age`-Dateien:
  `fuchs-shell-env.age` (nixos-config), `fuchs-mcp-obs-env.age`
  (sojus-core). Verschlüsselt gegen den SSH-Host-Key von nexus — nur mit
  dessen privatem Hostkey entschlüsselbar (root-only).
- **darwin26 nutzt sops-nix.** Definiert in `sojus-core/darwin26/secrets.nix`.
  Quelle ist `/etc/nixos/secrets.yaml` auf darwin26 (bearbeitet via `sudo sops
  /etc/nixos/secrets.yaml`), entschlüsselt beim Aktivieren nach
  `/etc/sojus/*.env` mit individuellen Owner/Mode (meist `0400`, Owner = der
  jeweilige Service-User).

**Welche Services nutzen welche Secrets** (darwin26, aus `secrets.nix` —
keine Werte, nur Variablennamen + Zielpfad):
| Secret | Pfad | Owner | Enthält (Variablennamen) |
|---|---|---|---|
| sojus/config | /etc/sojus/config.env | root | ANTHROPIC_API_KEY, PIPELINE_API_KEY, HA_TOKEN (für hermes-agent) |
| sojus/mcp-nextcloud | /etc/sojus/mcp-nextcloud.env | sojus-mcp | NEXTCLOUD_PASSWORD (wf, auch mcp-supplement) |
| sojus/fuchs-mcp-nextcloud-private | /etc/sojus/fuchs-mcp-nextcloud-private.env | sojus-mcp | NEXTCLOUD_PASSWORD (sh) |
| sojus/fuchs-mcp-homeassistant | .../fuchs-mcp-homeassistant.env | fuchs-mcp-homeassistant | HA_URL, HA_TOKEN |
| sojus/fuchs-mcp-immich | .../fuchs-mcp-immich.env | fuchs-mcp-immich | IMMICH_URL, IMMICH_API_KEY |
| sojus/fuchs-mcp-jellyfin | .../fuchs-mcp-jellyfin.env | fuchs-mcp-jellyfin | JELLYFIN_URL, JELLYFIN_API_KEY |
| sojus/fuchs-mcp-n8n | .../fuchs-mcp-n8n.env | fuchs-mcp-n8n | N8N_URL, N8N_API_KEY |
| sojus/fuchs-mcp-openproject | .../fuchs-mcp-openproject.env | fuchs-mcp-openproject | OPENPROJECT_URL, OPENPROJECT_API_KEY |
| sojus/fuchs-mcp-vikunja | .../fuchs-mcp-vikunja.env | fuchs-mcp-vikunja | VIKUNJA_URL, VIKUNJA_TOKEN |
| sojus/fuchs-mcp-anilist | .../fuchs-mcp-anilist.env | fuchs-mcp-anilist | ANILIST_ACCESS_TOKEN |
| sojus/fuchs-discord | .../fuchs-discord.env | fuchs-discord | DISCORD_BOT_TOKEN, DISCORD_ALLOWED_USERS |
| sojus/fuchs-email | .../fuchs-email.env | fuchs-email | EMAIL_PASS_HOFPAUSE, EMAIL_PASS_ARTEIGEN |
| sojus/mcp-approval | .../mcp-approval.env | mcp-approval | HA_TOKEN (Push bei Tier-3-Freigaben) |
| sojus/open-webui | .../open-webui.env | root | WEBUI_SECRET_KEY |

**Noch als Nix-Store-Klartext-Platzhalter** (bewusste MVP-Entscheidung, kein
echtes Secret-Management): `hermesApiKey` (hermes.nix) und
`approvalApiToken` (mcp-approval-service.nix + mcp-approval-proxy.nix +
fuchs-shell.nix, muss an allen drei Stellen identisch geändert werden).

---

## Offene Punkte aus diesem Durchlauf (2026-08-03)

- `/var/log`-ACL für `sojus` nicht gesetzt — braucht Jonas' sudo-Passwort.
- Deploy dieser Datei nach `/etc/sojus/SYSTEM_INFO.md` braucht ebenfalls
  root (Verzeichnis gehört root) — liegt bis dahin hier im Repo.
