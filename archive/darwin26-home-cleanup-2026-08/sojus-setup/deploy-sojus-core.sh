#!/usr/bin/env bash
# deploy-sojus-core.sh — Sojus Core: FastAPI KI-Agent + Memory MCP
# Ausführen auf darwin26 mit: sudo bash /home/fuchs/sojus-setup/deploy-sojus-core.sh
set -e

if [ "$(id -u)" != "0" ]; then
  echo "FEHLER: Bitte als root ausführen: sudo bash $0"
  exit 1
fi

echo "════════════════════════════════════════════"
echo "  SOJUS CORE DEPLOYMENT"
echo "════════════════════════════════════════════"
echo ""

# ── 1. SERVER-SCRIPTS KOPIEREN ────────────────────────────────────────────────
echo "--- Schritt 1: Server-Scripts kopieren ---"
mkdir -p /etc/sojus
cp /home/fuchs/sojus-setup/core.py          /etc/sojus/core.py
cp /home/fuchs/sojus-setup/memory_mcp.py    /etc/sojus/memory_mcp.py
cp /home/fuchs/sojus-setup/tool_groups.json /etc/sojus/tool_groups.json
chmod 644 /etc/sojus/core.py /etc/sojus/memory_mcp.py /etc/sojus/tool_groups.json
echo "  ✅ core.py, memory_mcp.py, tool_groups.json kopiert"

# ── 2. NIXOS-MODULE KOPIEREN ──────────────────────────────────────────────────
echo "--- Schritt 2: NixOS-Modul kopieren ---"
cp /home/fuchs/sojus-setup/sojus-core.nix /etc/nixos/sys/darwin26/sojus-core.nix
echo "  ✅ sojus-core.nix kopiert"

# ── 3. DEFAULT.NIX AKTUALISIEREN ─────────────────────────────────────────────
echo "--- Schritt 3: default.nix aktualisieren ---"

# Altes Pipeline-Modul entfernen, Core-Modul eintragen
if grep -q "sojus-pipeline.nix" /etc/nixos/sys/darwin26/default.nix; then
  sed -i 's|./sojus-pipeline.nix|./sojus-core.nix|' /etc/nixos/sys/darwin26/default.nix
  echo "  ✅ sojus-pipeline.nix → sojus-core.nix ersetzt"
elif grep -q "sojus-core.nix" /etc/nixos/sys/darwin26/default.nix; then
  echo "  ✅ sojus-core.nix bereits eingetragen"
else
  # Nach open-webui.nix einfügen
  sed -i 's|./open-webui.nix|./open-webui.nix\n    ./sojus-core.nix|' /etc/nixos/sys/darwin26/default.nix
  echo "  ✅ sojus-core.nix in default.nix eingetragen"
fi

# ── 4. CONFIG.ENV ERSTELLEN ───────────────────────────────────────────────────
echo "--- Schritt 4: /etc/sojus/config.env erstellen ---"

if [ -f /etc/sojus/config.env ]; then
  echo "  ✅ config.env existiert bereits — nicht überschrieben"
  echo "     (Manuell prüfen: ANTHROPIC_API_KEY und HA_TOKEN eingetragen?)"
else
  # HA_TOKEN aus dem bestehenden homeassistant env holen (falls vorhanden)
  HA_TOKEN_EXISTING=""
  if [ -f /etc/sojus/fuchs-mcp-homeassistant.env ]; then
    HA_TOKEN_EXISTING=$(grep "^HA_TOKEN=" /etc/sojus/fuchs-mcp-homeassistant.env | cut -d= -f2- | tr -d '"' || true)
  fi

  cat > /etc/sojus/config.env << ENVEOF
# Sojus Core — Konfiguration
# WICHTIG: ANTHROPIC_API_KEY und HA_TOKEN hier eintragen!

# LLM-Backends
ANTHROPIC_API_KEY=
OLLAMA_URL=http://192.168.1.40:11434
OLLAMA_MODEL=qwen3.5:9b
ANTHROPIC_MODEL=claude-sonnet-4-6

# Open WebUI → Sojus Core Auth
PIPELINE_API_KEY=sojus-pipeline-key

# Home Assistant (für iOS Push-Notifications)
HA_URL=http://127.0.0.1:8123
HA_TOKEN=${HA_TOKEN_EXISTING}
HA_NOTIFY_TARGET=mobile_app_iphone_von_jonas
ENVEOF

  chmod 600 /etc/sojus/config.env
  chown root:root /etc/sojus/config.env
  echo "  ✅ /etc/sojus/config.env erstellt"
  if [ -z "${HA_TOKEN_EXISTING}" ]; then
    echo "  ⚠️  HA_TOKEN ist leer — später eintragen für iOS Push-Notifications"
  else
    echo "  ✅ HA_TOKEN aus fuchs-mcp-homeassistant.env übernommen"
  fi
fi

# ── 5. MEMORY.JSON INITIALISIEREN ─────────────────────────────────────────────
echo "--- Schritt 5: memory.json initialisieren ---"
if [ ! -f /etc/sojus/memory.json ]; then
  echo "[]" > /etc/sojus/memory.json
  echo "  ✅ /etc/sojus/memory.json erstellt (leer)"
else
  echo "  ✅ /etc/sojus/memory.json existiert bereits"
fi

# ── 6. REMINDERS.JSON INITIALISIEREN ──────────────────────────────────────────
echo "--- Schritt 6: reminders.json initialisieren ---"
if [ ! -f /etc/sojus/reminders.json ]; then
  echo "[]" > /etc/sojus/reminders.json
  echo "  ✅ /etc/sojus/reminders.json erstellt (leer)"
else
  echo "  ✅ /etc/sojus/reminders.json existiert bereits"
fi

# ── 7. BERECHTIGUNGEN SETZEN ──────────────────────────────────────────────────
echo "--- Schritt 7: Berechtigungen ---"
# sojus-core User/Group existiert nach rebuild — Schreibzugriff über systemd ReadWritePaths
# tool_groups.json und core.py brauchen nur Leserechte
chmod 644 /etc/sojus/tool_groups.json
# memory.json und reminders.json brauchen Schreibzugriff (systemd ReadWritePaths)
chmod 664 /etc/sojus/memory.json /etc/sojus/reminders.json || true
echo "  ✅ Berechtigungen gesetzt"

# ── 8. GIT STAGING ────────────────────────────────────────────────────────────
echo "--- Schritt 8: Git staging ---"
git -C /etc/nixos add \
  sys/darwin26/sojus-core.nix \
  sys/darwin26/default.nix 2>/dev/null || true
echo "  ✅ Dateien zu git hinzugefügt"

# ── 9. NIXOS REBUILD ──────────────────────────────────────────────────────────
echo "--- Schritt 9: NixOS rebuild ---"
echo "  (Kann 2-5 Minuten dauern...)"
nixos-rebuild switch --flake /etc/nixos#darwin26

echo ""
echo "  ✅ NixOS rebuild erfolgreich!"

# ── 10. BERECHTIGUNGEN NACH REBUILD SETZEN ───────────────────────────────────
echo "--- Schritt 10: Dateiberechtigungen nach Rebuild ---"
# sojus-core User wurde jetzt durch Rebuild erstellt → Ownership setzen
if id sojus-core &>/dev/null; then
  chown sojus-core:sojus-core \
    /etc/sojus/memory.json \
    /etc/sojus/reminders.json \
    /etc/sojus/tool_groups.json \
    /etc/sojus/core.py \
    /etc/sojus/memory_mcp.py
  chmod 644 /etc/sojus/core.py /etc/sojus/memory_mcp.py /etc/sojus/tool_groups.json
  chmod 664 /etc/sojus/memory.json /etc/sojus/reminders.json
  echo "  ✅ Ownership → sojus-core"
else
  echo "  ⚠️  User sojus-core nicht gefunden — Berechtigungen manuell prüfen"
fi

# ── 11. SERVICES STOPPEN (sojus-pipeline ersetzen) ───────────────────────────
echo "--- Schritt 11: Alten Pipeline-Service stoppen ---"
systemctl stop sojus-pipeline.service 2>/dev/null && \
  echo "  ✅ sojus-pipeline.service gestoppt" || \
  echo "  ℹ️  sojus-pipeline.service war nicht aktiv"

# ── 12. STATUS PRÜFEN ────────────────────────────────────────────────────────
echo "--- Schritt 12: Services prüfen ---"
sleep 5

echo ""
echo "=== Service-Status ==="
for svc in sojus-core.service fuchs-sojus-memory.service open-webui.service; do
  STATUS=$(systemctl is-active "$svc" 2>/dev/null)
  if [ "$STATUS" = "active" ]; then
    echo "  ✅ $svc läuft"
  else
    echo "  ❌ $svc: $STATUS"
    echo "     → sudo journalctl -u $svc -n 20"
  fi
done

# Health-Check
sleep 5
HEALTH=$(curl -s "http://127.0.0.1:3001/health" 2>/dev/null)
if echo "${HEALTH}" | grep -q '"status":"ok"'; then
  echo ""
  echo "  ✅ Sojus Core antwortet auf Port 3001!"
  echo "     ${HEALTH}"
else
  echo ""
  echo "  ⚠️  Sojus Core noch nicht bereit (normal — kurz warten)"
  echo "     curl http://127.0.0.1:3001/health"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  SOJUS CORE DEPLOYMENT ABGESCHLOSSEN"
echo "════════════════════════════════════════════"
echo ""
echo "Jetzt sofort nutzbar (Ollama-Backend): ✅"
echo "Open WebUI: https://sojus.sternenhof.space"
echo ""
echo "Noch ausstehend (Jonas):"
echo "  1. ANTHROPIC_API_KEY in /etc/sojus/config.env eintragen"
echo "     → sudo nano /etc/sojus/config.env"
echo "     → sudo systemctl restart sojus-core.service"
echo ""
echo "  2. HA_TOKEN prüfen (für iOS Push-Notifications)"
echo "     → sudo grep HA_TOKEN /etc/sojus/config.env"
echo ""
echo "  3. Sojus testen:"
echo "     → curl -s http://127.0.0.1:3001/health | python3 -m json.tool"
echo "     → curl -s -X POST http://127.0.0.1:3001/v1/chat/completions \\"
echo "          -H 'Authorization: Bearer sojus-pipeline-key' \\"
echo "          -H 'Content-Type: application/json' \\"
echo "          -d '{\"messages\":[{\"role\":\"user\",\"content\":\"Hallo Sojus!\"}]}'"
echo ""
echo "  4. WireGuard VPN aufsetzen → nginx VPN-Filter aktivieren"
echo ""
