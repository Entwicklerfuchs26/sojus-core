{ config, pkgs, lib, ... }:

{
  # Fuchs braucht (anders als sojus) auf Nexus bisher nur NOPASSWD für
  # shutdown + nixos-rebuild dry-run (siehe hosts/nexus/host-config.nix
  # o.ä.). Für Sandbox-Tests reicht das nicht — hier NUR die exakten
  # Befehle für den sandbox-nexus-Testcontainer, kein blanket sudo.
  security.sudo.extraRules = [
    {
      users = [ "fuchs" ];
      commands = [
        { command = "/run/current-system/sw/bin/systemctl start container@sandbox-nexus.service";  options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl stop container@sandbox-nexus.service";   options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container@sandbox-nexus.service"; options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container@sandbox-nexus.service --no-pager"; options = [ "NOPASSWD" ]; }
        # Reprovisionierung des Test-Rootfs (siehe modules/ai/sojus.nix für
        # die gleiche Regel bei sojus, und die Begründung dazu).
        { command = "/run/current-system/sw/bin/rm -rf /var/lib/nixos-containers/sandbox-nexus"; options = [ "NOPASSWD" ]; }
      ];
    }
  ];
}
