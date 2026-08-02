#!/usr/bin/env bash
# deploy-fuchs-shell.sh — Shell MCP Server auf Nexus deployen
# Ausführen mit: sudo bash /home/fuchs/deploy-fuchs-shell.sh
set -e

if [ "$(id -u)" != "0" ]; then
  echo "FEHLER: Bitte als root ausführen: sudo bash $0"
  exit 1
fi

echo "════════════════════════════════════════════"
echo "  FUCHS-SHELL MCP DEPLOYMENT (Nexus)"
echo "════════════════════════════════════════════"

echo "--- Schritt 1: Server-Script kopieren ---"
mkdir -p /etc/sojus
cp /home/fuchs/fuchs-shell-server.py /etc/sojus/fuchs-shell-server.py
chmod 644 /etc/sojus/fuchs-shell-server.py
echo "  ✅ fuchs-shell-server.py kopiert"

echo "--- Schritt 2: Env-Datei erstellen ---"
if [ -f /etc/sojus/fuchs-shell.env ]; then
  echo "  ✅ fuchs-shell.env existiert bereits"
else
  cat > /etc/sojus/fuchs-shell.env << 'EOF'
SHELL_MCP_PORT=8012
SHELL_MCP_API_KEY=
EOF
  chmod 600 /etc/sojus/fuchs-shell.env
  chown root:root /etc/sojus/fuchs-shell.env
  echo "  ✅ fuchs-shell.env erstellt"
fi

echo "--- Schritt 3: NixOS-Modul kopieren ---"
cp /etc/nixos/nexus/fuchs-shell.nix /etc/nixos/nexus/fuchs-shell.nix 2>/dev/null || true
# Das .nix File liegt schon direkt in /etc/nixos/nexus/ (wurde von Claude Code geschrieben)
echo "  ✅ fuchs-shell.nix liegt in /etc/nixos/nexus/"

echo "--- Schritt 4: default.nix aktualisieren ---"
if grep -q "fuchs-shell.nix" /etc/nixos/nexus/default.nix; then
  echo "  ✅ fuchs-shell.nix bereits in default.nix eingetragen"
else
  sed -i 's|./ollama.nix|./ollama.nix\n    ./fuchs-shell.nix|' /etc/nixos/nexus/default.nix
  echo "  ✅ fuchs-shell.nix in default.nix eingetragen"
fi

echo "--- Schritt 5: Git staging ---"
git -C /etc/nixos add nexus/fuchs-shell.nix nexus/default.nix 2>/dev/null || true
echo "  ✅ Git staged"

echo "--- Schritt 6: NixOS rebuild ---"
echo "  (Kann 1-3 Minuten dauern...)"
nixos-rebuild switch --flake /etc/nixos#nexus

echo "--- Schritt 7: Berechtigungen nach Rebuild ---"
if id fuchs-shell &>/dev/null; then
  chown fuchs-shell:fuchs-shell /etc/sojus/fuchs-shell-server.py
  echo "  ✅ Ownership → fuchs-shell"
fi

echo "--- Schritt 8: Status prüfen ---"
sleep 5
STATUS=$(systemctl is-active fuchs-shell.service 2>/dev/null)
if [ "$STATUS" = "active" ]; then
  echo "  ✅ fuchs-shell.service läuft auf Port 8012"
else
  echo "  ❌ fuchs-shell.service: $STATUS"
  echo "     → sudo journalctl -u fuchs-shell.service -n 30"
fi

echo ""
echo "════════════════════════════════════════════"
echo "  DEPLOYMENT ABGESCHLOSSEN"
echo "════════════════════════════════════════════"
echo ""
echo "Shell MCP erreichbar unter: http://192.168.1.40:8012/mcp"
echo "→ Sojus-Core bekommt fuchs-shell als neuen MCP-Server"
