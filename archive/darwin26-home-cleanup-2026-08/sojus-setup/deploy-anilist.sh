#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "Usage: sudo bash deploy-anilist.sh <ANILIST_TOKEN>"
  echo ""
  echo "Token holen:"
  echo "  1. https://anilist.co/settings/developer → 'Create new client'"
  echo "     Name: Sojus, Redirect URL: https://anilist.co/api/v2/oauth/pin"
  echo "  2. Dann aufrufen:"
  echo "     https://anilist.co/api/v2/oauth/authorize?client_id=DEINE_ID&response_type=token"
  echo "  3. Token aus der URL nach dem Redirect kopieren"
  exit 1
fi

ANILIST_TOKEN="$1"

echo "=== Kopiere NixOS-Modul ==="
cp /home/fuchs/sojus-setup/fuchs-mcp-anilist.nix /etc/nixos/sys/darwin26/fuchs-mcp-anilist.nix

echo "=== Erstelle Env-Datei ==="
cat > /etc/sojus/fuchs-mcp-anilist.env << EOF
ANILIST_TOKEN=${ANILIST_TOKEN}
EOF
chmod 600 /etc/sojus/fuchs-mcp-anilist.env
chown root:root /etc/sojus/fuchs-mcp-anilist.env

echo "=== Aktualisiere default.nix ==="
sed -i 's|./fuchs-mcp-immich.nix|./fuchs-mcp-immich.nix\n    ./fuchs-mcp-anilist.nix|' /etc/nixos/sys/darwin26/default.nix

echo "=== Git add ==="
git -C /etc/nixos add sys/darwin26/fuchs-mcp-anilist.nix sys/darwin26/default.nix

echo "=== NixOS rebuild ==="
nixos-rebuild switch --flake /etc/nixos#darwin26

echo ""
echo "FERTIG! Service-Status:"
systemctl status fuchs-mcp-anilist.service --no-pager -l | head -20
