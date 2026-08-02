#!/usr/bin/env bash
set -e
echo "=== Kopiere aktualisiertes NixOS-Modul ==="
cp /home/fuchs/sojus-setup/fuchs-mcp-anilist.nix /etc/nixos/sys/darwin26/fuchs-mcp-anilist.nix
echo "=== Git add ==="
git -C /etc/nixos add sys/darwin26/fuchs-mcp-anilist.nix
echo "=== NixOS rebuild ==="
nixos-rebuild switch --flake /etc/nixos#darwin26
echo "=== Service-Status ==="
systemctl status fuchs-mcp-anilist.service --no-pager -l | head -25
