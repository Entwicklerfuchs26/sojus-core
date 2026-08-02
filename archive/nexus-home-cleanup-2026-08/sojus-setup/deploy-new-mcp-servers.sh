#!/usr/bin/env bash
# Deploy-Script für fuchs-mcp-n8n, -jellyfin, -immich, -ldap
# Ausführen auf darwin26 mit: bash /tmp/deploy-new-mcp-servers.sh
set -e

echo "=== Schritt 1: Server-Scripts kopieren ==="
sudo cp /tmp/fuchs-mcp-n8n-server.py      /etc/sojus/fuchs-mcp-n8n-server.py
sudo cp /tmp/fuchs-mcp-jellyfin-server.py /etc/sojus/fuchs-mcp-jellyfin-server.py
sudo cp /tmp/fuchs-mcp-immich-server.py   /etc/sojus/fuchs-mcp-immich-server.py
sudo cp /tmp/fuchs-mcp-ldap-server.py     /etc/sojus/fuchs-mcp-ldap-server.py
sudo chmod 644 /etc/sojus/fuchs-mcp-*-server.py

echo "=== Schritt 2: NixOS-Module kopieren ==="
sudo cp /tmp/fuchs-mcp-n8n.nix      /etc/nixos/sys/darwin26/fuchs-mcp-n8n.nix
sudo cp /tmp/fuchs-mcp-jellyfin.nix /etc/nixos/sys/darwin26/fuchs-mcp-jellyfin.nix
sudo cp /tmp/fuchs-mcp-immich.nix   /etc/nixos/sys/darwin26/fuchs-mcp-immich.nix
sudo cp /tmp/fuchs-mcp-ldap.nix     /etc/nixos/sys/darwin26/fuchs-mcp-ldap.nix

echo "=== Schritt 3: Env-Dateien anlegen (BITTE API-KEYS EINTRAGEN!) ==="

# n8n — API-Key aus: n8n.sternenhof.space → Settings → API → Create API Key
if [ ! -f /etc/sojus/fuchs-mcp-n8n.env ]; then
sudo tee /etc/sojus/fuchs-mcp-n8n.env > /dev/null << 'EOF'
N8N_URL=http://localhost:5678
N8N_API_KEY=BITTE_HIER_N8N_API_KEY_EINTRAGEN
EOF
sudo chmod 600 /etc/sojus/fuchs-mcp-n8n.env
sudo chown root:root /etc/sojus/fuchs-mcp-n8n.env
echo "  -> /etc/sojus/fuchs-mcp-n8n.env angelegt (API-Key eintragen!)"
else
echo "  -> /etc/sojus/fuchs-mcp-n8n.env existiert bereits"
fi

# Jellyfin — API-Key aus: media.sternenhof.space → Admin → API-Schlüssel → Hinzufügen
if [ ! -f /etc/sojus/fuchs-mcp-jellyfin.env ]; then
sudo tee /etc/sojus/fuchs-mcp-jellyfin.env > /dev/null << 'EOF'
JELLYFIN_URL=http://localhost:8096
JELLYFIN_API_KEY=BITTE_HIER_JELLYFIN_API_KEY_EINTRAGEN
EOF
sudo chmod 600 /etc/sojus/fuchs-mcp-jellyfin.env
sudo chown root:root /etc/sojus/fuchs-mcp-jellyfin.env
echo "  -> /etc/sojus/fuchs-mcp-jellyfin.env angelegt (API-Key eintragen!)"
else
echo "  -> /etc/sojus/fuchs-mcp-jellyfin.env existiert bereits"
fi

# Immich — API-Key aus: photos.sternenhof.space → Account → API-Schlüssel → Neu erstellen
if [ ! -f /etc/sojus/fuchs-mcp-immich.env ]; then
sudo tee /etc/sojus/fuchs-mcp-immich.env > /dev/null << 'EOF'
IMMICH_URL=http://localhost:2283
IMMICH_API_KEY=BITTE_HIER_IMMICH_API_KEY_EINTRAGEN
EOF
sudo chmod 600 /etc/sojus/fuchs-mcp-immich.env
sudo chown root:root /etc/sojus/fuchs-mcp-immich.env
echo "  -> /etc/sojus/fuchs-mcp-immich.env angelegt (API-Key eintragen!)"
else
echo "  -> /etc/sojus/fuchs-mcp-immich.env existiert bereits"
fi

# LDAP — Passwort aus sops secrets (ldap-root-pw)
if [ ! -f /etc/sojus/fuchs-mcp-ldap.env ]; then
sudo tee /etc/sojus/fuchs-mcp-ldap.env > /dev/null << 'EOF'
LDAP_URL=ldap://localhost
LDAP_BIND_DN=cn=admin,dc=sternenhof,dc=space
LDAP_BASE_DN=dc=sternenhof,dc=space
LDAP_PASSWORD=BITTE_HIER_LDAP_ADMIN_PASSWORT_EINTRAGEN
EOF
sudo chmod 600 /etc/sojus/fuchs-mcp-ldap.env
sudo chown root:root /etc/sojus/fuchs-mcp-ldap.env
echo "  -> /etc/sojus/fuchs-mcp-ldap.env angelegt (Passwort eintragen!)"
else
echo "  -> /etc/sojus/fuchs-mcp-ldap.env existiert bereits"
fi

echo ""
echo "=== Schritt 4: NixOS default.nix aktualisieren ==="
echo "Bitte manuell in /etc/nixos/sys/darwin26/default.nix folgende Zeilen vor dem letzten ']' einfügen:"
echo ""
echo "    ./fuchs-mcp-n8n.nix"
echo "    ./fuchs-mcp-jellyfin.nix"
echo "    ./fuchs-mcp-immich.nix"
echo "    ./fuchs-mcp-ldap.nix"
echo ""

echo "=== Schritt 5: Git add ==="
echo "Danach ausführen:"
echo "  sudo git -C /etc/nixos add sys/darwin26/fuchs-mcp-n8n.nix sys/darwin26/fuchs-mcp-jellyfin.nix sys/darwin26/fuchs-mcp-immich.nix sys/darwin26/fuchs-mcp-ldap.nix"
echo ""
echo "=== Schritt 6: NixOS rebuild ==="
echo "  sudo nixos-rebuild switch --flake /etc/nixos#darwin26"
echo ""
echo "WICHTIG: Erst API-Keys in die .env-Dateien eintragen, dann rebuild!"
