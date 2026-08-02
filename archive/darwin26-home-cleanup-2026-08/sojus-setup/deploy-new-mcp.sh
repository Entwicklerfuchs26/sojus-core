#!/usr/bin/env bash
set -e

echo "=== Kopiere Server-Scripts nach /etc/sojus/ ==="
cp /home/fuchs/sojus-setup/fuchs-mcp-vikunja-server.py /etc/sojus/fuchs-mcp-vikunja-server.py
cp /home/fuchs/sojus-setup/fuchs-mcp-homeassistant-server.py /etc/sojus/fuchs-mcp-homeassistant-server.py
chmod 644 /etc/sojus/fuchs-mcp-vikunja-server.py /etc/sojus/fuchs-mcp-homeassistant-server.py

echo "=== Kopiere NixOS-Module nach /etc/nixos/sys/darwin26/ ==="
cp /home/fuchs/sojus-setup/fuchs-mcp-vikunja.nix /etc/nixos/sys/darwin26/fuchs-mcp-vikunja.nix
cp /home/fuchs/sojus-setup/fuchs-mcp-homeassistant.nix /etc/nixos/sys/darwin26/fuchs-mcp-homeassistant.nix

echo "=== Erstelle Env-Datei für Vikunja ==="
cat > /etc/sojus/fuchs-mcp-vikunja.env << 'EOF'
VIKUNJA_URL=http://localhost:3456
VIKUNJA_TOKEN=[REDACTED — von Sojus beim Archivieren am 2026-08-03 entfernt, echter JWT war im Klartext]
EOF
chmod 600 /etc/sojus/fuchs-mcp-vikunja.env
chown root:root /etc/sojus/fuchs-mcp-vikunja.env

echo "=== Erstelle Platzhalter-Env für Home Assistant ==="
cat > /etc/sojus/fuchs-mcp-homeassistant.env << 'EOF'
HA_URL=http://localhost:8123
HA_TOKEN=PLACEHOLDER_BITTE_ERSETZEN
HA_NOTIFY_TARGET=mobile_app_iphone
EOF
chmod 600 /etc/sojus/fuchs-mcp-homeassistant.env
chown root:root /etc/sojus/fuchs-mcp-homeassistant.env

echo "=== Aktualisiere default.nix ==="
sed -i 's|./mcp-openproject.nix|./mcp-openproject.nix\n    ./fuchs-mcp-vikunja.nix\n    ./fuchs-mcp-homeassistant.nix|' /etc/nixos/sys/darwin26/default.nix

echo "=== Git add ==="
git -C /etc/nixos add sys/darwin26/fuchs-mcp-vikunja.nix sys/darwin26/fuchs-mcp-homeassistant.nix sys/darwin26/default.nix

echo "=== NixOS rebuild ==="
nixos-rebuild switch --flake /etc/nixos#darwin26

echo "FERTIG!"
