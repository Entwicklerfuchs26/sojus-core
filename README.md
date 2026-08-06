# Sojus Core

NixOS-Flake mit den MCP-Services und der Agent-Engine für Jonas' Digital-Life-OS
("Sojus"), verteilt über zwei Hosts: `nexus` (Gaming-PC, Desktop-Apps) und
`darwin26` (Server, Cloud-Dienste + Agent).

## Aktueller Stand

**Hermes ist die Agent-Engine**, jetzt als parametrisiertes Modul
(`modules/sojus-agent.nix`) statt fest verdrahtet — jede Instanz (siehe
`instances/`) bekommt ihren eigenen User, Service, Port und ihre eigene
SOUL.md. Jonas' Instanz läuft als `hermes-agent.service` auf darwin26, Port
3002, OpenAI-kompatible API, Modell `claude-haiku-4-5-20251001`, mit
`tool_search` (mode: on) über alle angebundenen MCP-Server. Open WebUI
(`sojus.sternenhof.space`) spricht mit Hermes. Eine zweite Instanz ("kaira",
Port 3010) läuft eigenständig daneben, ohne Zugriff auf Jonas' Daten.

Der frühere Agent-Stack ("Sojus Core", core.py-basiert) ist archiviert, siehe
[`archive/sojus-core-legacy/`](archive/sojus-core-legacy/) — Hermes ersetzt ihn
vollständig, inklusive dem eingebauten Memory (das alte `fuchs-sojus-memory`
MCP war redundant dazu).

## Struktur

```
modules/    Parametrisierte NixOS-Module: Agent-Engine, MCP-Liste, Sandbox, Secrets
instances/  Konkrete Instanzen (jonas, kaira) — Parameter für modules/
darwin26/   NixOS-Module für darwin26 (Server): MCP-Server, Secrets, Approval-Proxy
nexus/      NixOS-Module für nexus (Desktop): 12 lokale MCP-Services (Ports 9000-9011)
scripts/    Python-Quellcode der MCP-Server, referenziert aus den .nix-Modulen
config/     Tool-Konfiguration
archive/    Stillgelegte, aber nicht gelöschte Komponenten (siehe unten)
```

Eingebunden wird das Ganze als Flake-Input `sojus-core` in die jeweilige
Host-Config (`/etc/nixos` auf nexus bzw. darwin26) — siehe `flake.nix` für die
exportierten `nixosModules.nexus` / `nixosModules.darwin26`.

## Deploy

```bash
git pull
sudo nixos-rebuild switch --flake /etc/nixos#<nexus|darwin26> --update-input sojus-core
```

`--update-input` ist zwingend, da `sojus-core` ein lokaler `path:`-Flake-Input
ist und sonst der gecachte narHash aus `flake.lock` verwendet wird. Bei reinen
Config-Inhalt-Änderungen (z.B. JSON-Dateien über Activation-Scripts) zusätzlich
den betroffenen Service manuell neu starten — ein `nixos-rebuild switch` löst
nur dann einen Service-Restart aus, wenn sich die Unit-Definition selbst ändert.

## Archiv

`archive/sojus-core-legacy/` enthält den vor-Hermes-Agent-Stack (nicht mehr in
`default.nix` importiert, keine laufenden Services mehr):

- `sojus-core.nix` — der alte core.py-Agent + `fuchs-sojus-memory` MCP
- `sojus-pipeline.nix` — OpenAI→n8n-Bridge, war schon vor der Archivierung nicht mehr eingebunden
- `core.py`, `memory_mcp.py`, `tool_router.py`, `sojus-pipeline.py` — zugehöriger Python-Code
- `tool_groups.json`, `tool_tiers.json` — Tool-Tiering-Config des alten Agents

Bewusst nicht gelöscht, falls einzelne Konzepte (z.B. das Tier-Gating für
gefährliche Shell-Befehle) für spätere Hermes-Erweiterungen relevant werden.

`archive/hermes-sojus-api-legacy-2026-08/` enthält die Vorgänger von
`modules/sojus-agent.nix`:

- `hermes.nix` — das frühere, fest verdrahtete Hermes-Modul (nur Jonas' Instanz)
- `sojus-api.nix` — die frühere, eigenständige Chat-API (options.services.sojusApi)

Beide Funktionalitäten stecken jetzt gebündelt in `modules/sojus-agent.nix`,
instanziiert über `instances/jonas.nix` (identische User-/Port-/Key-Werte, rein
funktional unverändert) und `instances/kaira.nix`.
