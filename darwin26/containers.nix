{ config, pkgs, lib, ... }:

{
  # Sandbox-Container für Hermes: isolierte Kopie von sojus-core zum Testen
  # von Prompt-/MCP-/Memory-Änderungen, bevor sie live gehen. Startet nicht
  # automatisch — nur wenn Hermes (über fuchs-sandbox-control) ihn braucht.
  containers.sandbox-sojus = {
    autoStart = false;
    privateNetwork = true;
    hostAddress = "10.10.1.1";
    localAddress = "10.10.1.2";

    bindMounts = {
      "/var/lib/sojus" = {
        hostPath = "/var/lib/sandbox-sojus";
        isReadOnly = false;
      };
    };

    config = { config, pkgs, ... }: {
      system.stateVersion = "25.05";

      users.users.sojus = {
        isSystemUser = true;
        group = "sojus";
        home = "/var/lib/sojus";
        createHome = true;
      };
      users.groups.sojus = {};

      environment.systemPackages = with pkgs; [
        git
        python3
        curl
      ];
    };
  };

  # Host-seitiges Verzeichnis für die sojus-core-Testkopie. Gehört fuchs, damit
  # rsync (initiale Kopie + spätere sandbox-sojus sync) ohne sudo läuft.
  systemd.tmpfiles.rules = [
    "d /var/lib/sandbox-sojus 0750 fuchs users -"
  ];
}
