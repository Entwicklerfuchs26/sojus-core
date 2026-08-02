#!/usr/bin/env bash
set -e
# Fügt sojus.sternenhof.space zur DNS-Config hinzu
sed -i 's|/tasks.sternenhof.space/192.168.1.26"|/tasks.sternenhof.space/192.168.1.26"\n        "/sojus.sternenhof.space/192.168.1.26"|'   /etc/nixos/sys/darwin26/dhcp_dns.nix

# Prüfen ob es geklappt hat
grep sojus /etc/nixos/sys/darwin26/dhcp_dns.nix && echo 'DNS-Eintrag hinzugefügt!'

git -C /etc/nixos add sys/darwin26/dhcp_dns.nix
nixos-rebuild switch --flake /etc/nixos#darwin26
echo 'Fertig! sojus.sternenhof.space zeigt jetzt auf 192.168.1.26'
