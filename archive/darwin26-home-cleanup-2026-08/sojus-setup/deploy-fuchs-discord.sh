#!/usr/bin/env bash
# deploy-fuchs-discord.sh — Discord Bot + MCP auf darwin26 deployen
# Auf darwin26 ausführen mit: sudo bash /etc/sojus/deploy-fuchs-discord.sh
set -e

if [ "$(id -u)" != "0" ]; then
  echo "FEHLER: Bitte als root ausführen: sudo bash $0"
  exit 1
fi

echo "════════════════════════════════════════════"
echo "  FUCHS-DISCORD DEPLOYMENT (darwin26)"
echo "════════════════════════════════════════════"

echo "--- Schritt 1: Server-Script kopieren ---"
mkdir -p /etc/sojus
cp /home/fuchs/sojus-setup/fuchs-discord-server.py /etc/sojus/fuchs-discord-server.py
chmod 644 /etc/sojus/fuchs-discord-server.py
echo "  ✅ fuchs-discord-server.py kopiert"

echo "--- Schritt 2: Env-Datei erstellen ---"
if [ -f /etc/sojus/fuchs-discord.env ]; then
  echo "  ✅ fuchs-discord.env existiert bereits — Token prüfen:"
  grep -v TOKEN /etc/sojus/fuchs-discord.env
else
  cat > /etc/sojus/fuchs-discord.env << 'EOF'
# Discord Bot Token (aus Discord Developer Portal)
DISCORD_BOT_TOKEN=HIER_TOKEN_EINTRAGEN

# Sojus-Core Verbindung
SOJUS_CORE_URL=http://127.0.0.1:3001
SOJUS_PIPELINE_KEY=sojus-pipeline-key

# MCP Server Port (nur lokal, kein öffentlicher Firewall-Port)
DISCORD_MCP_PORT=8011

# Erlaubte Discord User-IDs (kommagetrennt, leer = alle blockiert außer Bot-Antworten)
# Developer Mode aktivieren → Rechtsklick auf User → ID kopieren
DISCORD_ALLOWED_USERS=
EOF
  chmod 600 /etc/sojus/fuchs-discord.env
  chown root:root /etc/sojus/fuchs-discord.env
  echo "  ✅ fuchs-discord.env erstellt"
  echo "  ⚠️  DISCORD_BOT_TOKEN und DISCORD_ALLOWED_USERS noch eintragen!"
fi

echo "--- Schritt 3: NixOS-Modul kopieren ---"
cp /home/fuchs/sojus-setup/fuchs-discord.nix /etc/nixos/sys/darwin26/fuchs-discord.nix
echo "  ✅ fuchs-discord.nix kopiert"

echo "--- Schritt 4: default.nix aktualisieren ---"
if grep -q "fuchs-discord.nix" /etc/nixos/sys/darwin26/default.nix; then
  echo "  ✅ fuchs-discord.nix bereits eingetragen"
else
  # Nach dem letzten bestehenden MCP-Modul einfügen
  sed -i 's|./fuchs-mcp-anilist.nix|./fuchs-mcp-anilist.nix\n    ./fuchs-discord.nix|' /etc/nixos/sys/darwin26/default.nix
  echo "  ✅ fuchs-discord.nix in default.nix eingetragen"
fi

echo "--- Schritt 5: core.py aktualisieren (Discord + Shell in MCP_SERVERS) ---"
# Füge die neuen Server ein, falls noch nicht vorhanden
if grep -q "fuchs-discord" /etc/sojus/core.py; then
  echo "  ✅ fuchs-discord bereits in core.py"
else
  sed -i 's|"fuchs-sojus-memory":.*"http://127.0.0.1:8010/mcp",|"fuchs-sojus-memory":      "http://127.0.0.1:8010/mcp",\n    "fuchs-discord":           "http://127.0.0.1:8011/mcp",\n    "fuchs-shell":             "http://192.168.1.40:8012/mcp",|' /etc/sojus/core.py
  echo "  ✅ fuchs-discord + fuchs-shell in core.py eingetragen"
fi

echo "--- Schritt 6: core.py in sojus-setup synchronisieren ---"
cp /etc/sojus/core.py /home/fuchs/sojus-setup/core.py
echo "  ✅ sojus-setup/core.py synchronisiert"

echo "--- Schritt 7: Git staging ---"
git -C /etc/nixos add sys/darwin26/fuchs-discord.nix sys/darwin26/default.nix 2>/dev/null || true
echo "  ✅ Git staged"

echo "--- Schritt 8: NixOS rebuild ---"
nixos-rebuild switch --flake /etc/nixos#darwin26

echo "--- Schritt 9: Berechtigungen + Sojus-Core neu starten ---"
if id fuchs-discord &>/dev/null; then
  chown fuchs-discord:fuchs-discord /etc/sojus/fuchs-discord-server.py
fi
systemctl restart sojus-core.service
echo "  ✅ sojus-core neu gestartet (kennt jetzt fuchs-discord + fuchs-shell)"

echo "--- Schritt 10: Status prüfen ---"
sleep 8
for svc in fuchs-discord.service sojus-core.service; do
  STATUS=$(systemctl is-active "$svc" 2>/dev/null)
  if [ "$STATUS" = "active" ]; then
    echo "  ✅ $svc läuft"
  else
    echo "  ❌ $svc: $STATUS → sudo journalctl -u $svc -n 20"
  fi
done

echo ""
echo "════════════════════════════════════════════"
echo "  DISCORD DEPLOYMENT ABGESCHLOSSEN"
echo "════════════════════════════════════════════"
echo ""
echo "Noch ausstehend (Jonas):"
echo "  1. Discord Bot Token erstellen:"
echo "     https://discord.com/developers/applications"
echo "     → Neue Application → Bot → Token kopieren"
echo "     → 'Message Content Intent' aktivieren"
echo "  2. Token eintragen:"
echo "     sudo nano /etc/sojus/fuchs-discord.env"
echo "  3. Deine Discord User-ID eintragen (DISCORD_ALLOWED_USERS)"
echo "     → Discord Developer Mode → Rechtsklick auf dich → 'ID kopieren'"
echo "  4. Bot in einen Server einladen (OAuth2 → URL Generator → bot scope)"
echo "  5. Service neu starten:"
echo "     sudo systemctl restart fuchs-discord.service"
