# Parametrisierte Sandbox-Container-Vorlage — Analogon zu `containers.sandbox-sojus`
# aus darwin26/containers.nix, aber pro Instanz. Isolierte Kopie für spätere
# Selbst-Entwicklung/-Tests der jeweiligen Agent-Instanz, startet nicht
# automatisch. Bewusst NICHT dasselbe wie `sandbox-darwin` (Systemebene, ein
# einziger, host-weiter Container für /etc/nixos-Tests) — das bleibt
# unverändert in containers.nix.
# hostAddress/localAddress: jede Instanz braucht ihr eigenes /30 — sandbox-sojus
# belegt bereits 10.10.1.x, sandbox-darwin 10.10.2.x (siehe containers.nix).
# Neue Instanzen fortlaufend ab 10.10.3.x vergeben und hier explizit angeben.
{ instanceName
, hostAddress  ? "10.10.3.1"
, localAddress ? "10.10.3.2"
}:
{ config, pkgs, lib, ... }:

let
  containerName = "sandbox-${instanceName}";
  hostVarDir = "/var/lib/${containerName}";
in {
  containers.${containerName} = {
    autoStart = false;
    privateNetwork = true;
    inherit hostAddress localAddress;

    bindMounts = {
      "/var/lib/${instanceName}" = {
        hostPath = hostVarDir;
        isReadOnly = false;
      };
    };

    config = { config, pkgs, ... }: {
      system.stateVersion = "25.05";

      users.users.${instanceName} = {
        isSystemUser = true;
        group = instanceName;
        home = "/var/lib/${instanceName}";
        createHome = true;
      };
      users.groups.${instanceName} = {};

      environment.systemPackages = with pkgs; [
        git
        python3
        curl
      ];
    };
  };

  systemd.tmpfiles.rules = [
    "d ${hostVarDir} 0750 fuchs users -"
  ];
}
