#!/bin/sh
set -e

SETUP=/home/fuchs/sojus-setup

# ─── mcp-nextcloud (Port 8000) ───────────────────────────────────────────────
cp $SETUP/mcp-nextcloud.nix /etc/nixos/sys/darwin26/mcp-nextcloud.nix
echo "OK mcp-nextcloud.nix kopiert"

# default.nix: mcp-nextcloud.nix nur einmal eintragen
if ! grep -q 'mcp-nextcloud.nix' /etc/nixos/sys/darwin26/default.nix; then
  sed -i 's|./n8n.nix|./n8n.nix\n    ./mcp-nextcloud.nix|' /etc/nixos/sys/darwin26/default.nix
  echo "OK mcp-nextcloud.nix in default.nix eingetragen"
else
  echo "OK mcp-nextcloud.nix bereits in default.nix"
fi

mkdir -p /etc/sojus
printf 'NEXTCLOUD_PASSWORD=[REDACTED — von Sojus beim Archivieren am 2026-08-03 entfernt, echtes Passwort war im Klartext]\n' > /etc/sojus/mcp-nextcloud.env
chmod 600 /etc/sojus/mcp-nextcloud.env
chown root:root /etc/sojus/mcp-nextcloud.env
echo "OK Credentials gesichert"

# ─── mcp-supplement (Port 8001) ──────────────────────────────────────────────
cp $SETUP/mcp-supplement.nix /etc/nixos/sys/darwin26/mcp-supplement.nix
echo "OK mcp-supplement.nix kopiert"

# default.nix: mcp-supplement.nix nur einmal eintragen
if ! grep -q 'mcp-supplement.nix' /etc/nixos/sys/darwin26/default.nix; then
  sed -i 's|./mcp-nextcloud.nix|./mcp-nextcloud.nix\n    ./mcp-supplement.nix|' /etc/nixos/sys/darwin26/default.nix
  echo "OK mcp-supplement.nix in default.nix eingetragen"
else
  echo "OK mcp-supplement.nix bereits in default.nix"
fi

cp $SETUP/mcp-supplement/server.py /etc/sojus/mcp-supplement-server.py
chmod 644 /etc/sojus/mcp-supplement-server.py
chown root:root /etc/sojus/mcp-supplement-server.py
echo "OK mcp-supplement-server.py nach /etc/sojus/ kopiert"

echo ""
echo "═══ Aktueller Stand default.nix (mcp/n8n) ═══"
grep -n "mcp\|n8n" /etc/nixos/sys/darwin26/default.nix
