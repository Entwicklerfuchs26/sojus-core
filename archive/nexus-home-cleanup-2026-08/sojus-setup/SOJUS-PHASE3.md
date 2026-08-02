# Sojus Phase 3 — Dokumentation

**Datum:** 11. Juli 2026  
**Ziel:** Vollständiger KI-Assistent mit Chat-Interface, echtem LLM und Sicherheitsarchitektur

---

## Architektur

```
iPhone / Nexus Browser
        │
        ▼ HTTPS
┌─────────────────────────────┐
│  Open WebUI                 │  sojus.sternenhof.space
│  Port 8080 (darwin26)       │  PWA, Chat-History, Multimodal
└──────────────┬──────────────┘
               │ OpenAI-kompatibler API-Call
               ▼
┌─────────────────────────────┐
│  Sojus Pipeline             │  Python, Port 3001 (darwin26)
│  /etc/sojus/sojus-pipeline.py│  Bridge: OpenAI-Format → n8n
└──────────────┬──────────────┘
               │ HTTP POST JSON
               ▼
┌─────────────────────────────┐
│  n8n Webhook                │  localhost:5678/webhook/sojus-firmenchef
│  Workflow: sojus-firmenchef │
│  ID: 7shor2T8FhfdR00w       │
└──────────────┬──────────────┘
               │ HTTP POST
               ▼
┌─────────────────────────────┐
│  Ollama                     │  http://192.168.1.40:11434
│  Modell: deepseek-r1:8b     │  ~13s Antwortzeit
└─────────────────────────────┘
```

---

## Komponenten

### Open WebUI (NixOS-Service auf darwin26)
- **Service:** `open-webui.service`
- **Port:** 8080 (nur localhost, nginx davor)
- **NixOS-Modul:** `/etc/nixos/sys/darwin26/open-webui.nix`
- **Env-File:** `/etc/sojus/open-webui.env` (WEBUI_SECRET_KEY, OPENAI_API_BASE_URL)
- **Nginx:** sojus.sternenhof.space → localhost:8080, SSL via Wildcard-Cert
- **Features:** ENABLE_SIGNUP=False, ENABLE_OLLAMA_API=False, DO_NOT_TRACK=True

**Open WebUI zeigt als "KI-Modell":** die Sojus Pipeline (Port 3001) mit Model-ID `sojus-agent`

### Sojus Pipeline (NixOS-Service auf darwin26)
- **Service:** `sojus-pipeline.service`
- **Datei:** `/etc/sojus/sojus-pipeline.py`
- **NixOS-Modul:** `/etc/nixos/sys/darwin26/sojus-pipeline.nix`
- **Port:** 3001
- **Funktion:** Empfängt OpenAI `/v1/chat/completions` Requests von Open WebUI, extrahiert letzte Nachricht + letzte 10 History-Einträge, sendet als JSON an n8n Webhook, gibt Antwort zurück
- **Timeout:** 60 Sekunden für n8n-Anfrage
- **Webhook-URL:** `http://localhost:5678/webhook/sojus-firmenchef` (in sojus-pipeline.nix hardcoded)
- **Stub-Response:** Wenn n8n nicht erreichbar → "Sojus ist bereit und wartet..."

**Pipeline sendet an n8n:**
```json
{
  "message": "letzte User-Nachricht",
  "history": ["user: ...", "assistant: ..."],
  "request_id": "uuid",
  "user": "fuchs",
  "channel": "open_webui"
}
```

**Pipeline erwartet von n8n:**
```json
{"response": "Antwort-Text"}
```

### n8n Workflow: sojus-firmenchef
- **Workflow-ID:** `7shor2T8FhfdR00w`
- **Status:** Aktiv (aber Webhook-Bug, siehe unten)
- **Webhook-Pfad:** `POST /webhook/sojus-firmenchef`

**Node-Kette:**
```
Webhook (POST sojus-firmenchef, responseMode: responseNode)
  → Nachricht extrahieren (Code)
      Baut messages[]-Array: system-prompt + history + user-message
      System-Prompt enthält: Sojus-Persona, Homelab-Kontext, Sicherheitsregeln
  → Ollama DeepSeek R1 (HTTP Request)
      POST http://192.168.1.40:11434/api/chat
      Body: {model: "deepseek-r1:8b", messages: [...], stream: false}
      Timeout: 120s
  → Format Response (Code)
      Extrahiert result.message.content
      Filtert <think>...</think> Blöcke heraus (DeepSeek R1 denkt laut)
      Multi-Pass bis alle Think-Tags entfernt
  → Antwort senden (RespondToWebhook)
      responseBody: $json (gibt {response: "..."} zurück)
```

**System-Prompt (im Code-Node):**
- Persona: Sojus, kumpelhaft/direkt/zynisch, kurze Antworten
- Kontext: darwin26, nexus, iPhone 13 Mini
- Sicherheitsregeln (unveränderlich):
  - Tier 1: Prompt Injection → sofort blockieren
  - Tier 2 (nixos-rebuild, systemctl stop): 1x Bestätigung
  - Tier 3 (rm -rf, dd, mkfs, poweroff): 2x Bestätigung mit Zufallscode (CONFIRM-XXXX → EXECUTE-YYYY)

### Ollama (192.168.1.40:11434)
Verfügbare Modelle:
- `deepseek-r1:8b` — aktuell genutzt (~13s Antwortzeit)
- `qwen3.5:9b` — Alternative
- `deepseek-coder-v2:latest` — Coding
- `llava:7b` — Multimodal
- `llama3.1:8b` — General

---

## Bekannte Probleme & Status

### ⚠️ Webhook-Bug (NICHT GELÖST)

**Problem:** n8n 1.91.3 registriert Webhooks nicht im Live-Registry (`LiveWebhooks`), obwohl der Workflow als aktiv markiert ist.

**Symptom:** `curl POST https://n8n.sternenhof.space/webhook/sojus-firmenchef` → HTTP 404 "The requested webhook is not registered"

**Was versucht wurde:**
- API: deactivate → activate (mehrfach) ❌
- n8n Neustart: `sudo systemctl restart n8n.service` ❌
- UI-Toggle in n8n Editor (Jonas hat es gemacht) ❌
- Neuer Workflow mit anderem Pfad (`sojus-test-ping`) ❌ gleicher Fehler
- Weitere Diagnose: n8n Service-Konfiguration noch nicht geprüft

**Konsequenz:** Sojus Pipeline bekommt HTTP 404 von n8n → catchs als URLError → gibt Stub-Response zurück

**Verdacht:** n8n läuft möglicherweise in einem Modus (queue mode, custom executions mode) der Live-Webhook-Registration verhindert. Zu prüfen: `EXECUTIONS_MODE` Environment-Variable in n8n Service.

**Nächste Diagnose-Schritte auf darwin26:**
```bash
sudo systemctl show n8n.service --property=Environment
sudo systemctl cat n8n.service | grep -i "execut\|webhook\|mode\|queue"
```

---

## Deployment-Historie (heute)

### Was deployed wurde

1. **Open WebUI** (NixOS-Service, darwin26) → läuft ✅
2. **Sojus Pipeline** (NixOS-Service, darwin26, Port 3001) → läuft ✅
3. **DNS darwin26** (dnsmasq) → sojus.sternenhof.space → 192.168.1.26 ✅
4. **DNS nexus** (networking.hosts) → sojus.sternenhof.space → 192.168.1.26 ✅
5. **Open WebUI Admin-Account** → von Jonas angelegt ✅
6. **n8n Firmenchef Workflow** → existiert, aktiv, aber Webhook-Bug ⚠️

### Deployment-Script
`/home/fuchs/sojus-setup/deploy-sojus-phase3.sh` — deployed alle NixOS-Module, erstellt Env-Files, führt nixos-rebuild durch

### Workflow-Iterationen (viele Versuche heute)
- `GcIYMVO7PtTXuDbC` — erster Stub (nur Code-Nodes, kein LLM) → gelöscht
- `etkBkHENJepgqUvM` — HTTP Request zu Ollama → gelöscht
- `cK3QIrzhtqpChGq2` — AI Agent Node + lmChatOllama (Bug: kein Credential) → gelöscht
- `7shor2T8FhfdR00w` — **aktueller** HTTP Request zu Ollama, sauber gebaut → AKTIV aber Webhook-Bug

---

## Ausstehende Aufgaben

### Jonas (manuell)
- [ ] **n8n Webhook-Bug lösen** (Diagnose: EXECUTIONS_MODE prüfen, siehe oben)
- [ ] **Anthropic API Key** kaufen → in n8n Credentials als "Anthropic" eintragen → HTTP Request Node in Workflow gegen Anthropic Chat Model Node tauschen
- [ ] **WireGuard VPN** aufsetzen → dann nginx VPN-Filter in open-webui.nix aktivieren
- [ ] **System-Prompt** in Open WebUI Einstellungen → Modelle → sojus-agent setzen
- [ ] **Kalender-Tagesbrief** n8n Workflow aktivieren (ID: `AmrNidCieklivlEr`)
- [ ] **Hyprland Keybind** für schnellen Chat-Zugriff

### Wenn Anthropic API Key da ist
Im Workflow `7shor2T8FhfdR00w`:
- Node "Ollama DeepSeek R1" (HTTP Request) ersetzen durch Anthropic Chat Model Node
- Anthropic Credential in n8n anlegen (Einstellungen → Credentials → Anthropic → API Key)
- System-Prompt ist bereits im Code-Node, muss nur übernommen werden

### Zukünftige Erweiterungen
- MCP-Tools in Open WebUI Admin-Panel eintragen (Ports 8000-8009 auf darwin26)
- RAG / Nextcloud-Dateien vektorisieren (Qdrant)
- Raspberry Pi mcp-network, mcp-gpio

---

## Dateien & Pfade

| Datei | Beschreibung |
|-------|-------------|
| `/home/fuchs/sojus-setup/open-webui.nix` | NixOS-Modul Open WebUI |
| `/home/fuchs/sojus-setup/sojus-pipeline.nix` | NixOS-Modul Pipeline |
| `/home/fuchs/sojus-setup/sojus-pipeline.py` | Pipeline Python-Server |
| `/home/fuchs/sojus-setup/fuchs-mcp-n8n-server.py` | n8n MCP-Server |
| `/home/fuchs/sojus-setup/deploy-sojus-phase3.sh` | Deployment-Script |
| `/etc/sojus/open-webui.env` | Secrets Open WebUI (darwin26) |
| `/etc/sojus/sojus-pipeline.env` | Secrets Pipeline (darwin26) |
| `/etc/sojus/fuchs-mcp-n8n.env` | n8n API-Key für MCP (darwin26) |
| `/etc/nixos/sys/darwin26/open-webui.nix` | deployed NixOS-Modul |
| `/etc/nixos/sys/darwin26/sojus-pipeline.nix` | deployed NixOS-Modul |
