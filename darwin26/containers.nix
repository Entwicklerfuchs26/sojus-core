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

  # Sandbox-Container für darwin26-Systemebene: isolierte Kopie von /etc/nixos
  # zum Testen von NixOS-Modulen (Services, Nutzer, Pakete) inkl. echtem
  # nixos-rebuild switch, ohne den echten Host anzufassen. sojus-core wird
  # read-only mit reingemountet, weil sys/darwin26/default.nix es als
  # path:-Flake-Input referenziert (sonst evaluiert die Kopie nicht).
  containers.sandbox-darwin = {
    autoStart = false;
    privateNetwork = true;
    hostAddress = "10.10.2.1";
    localAddress = "10.10.2.2";

    bindMounts = {
      "/var/lib/darwin" = {
        hostPath = "/var/lib/sandbox-darwin";
        isReadOnly = false;
      };
      "/home/fuchs/sojus-core" = {
        hostPath = "/home/fuchs/sojus-core";
        isReadOnly = true;
      };
    };

    config = { config, pkgs, ... }: {
      system.stateVersion = "25.05";

      # Normaler User mit passwortlosem wheel-sudo NUR innerhalb des
      # Containers — der Container selbst ist die Isolationsgrenze, hier
      # geht's ums Testen von nixos-rebuild switch, nicht um Härtung.
      # uid/gid fest vergeben (statt auto-vergeben), damit die ACL auf dem
      # Host-Verzeichnis stabil bleibt und nicht bei jedem Rebuild verrutscht.
      users.users.sojus = {
        isNormalUser = true;
        uid = 1000;
        group = "sojus";
        home = "/var/lib/sojus";
        createHome = true;
        extraGroups = [ "wheel" ];
      };
      users.groups.sojus.gid = 1000;
      security.sudo.wheelNeedsPassword = false;

      nix.settings.experimental-features = [ "nix-command" "flakes" ];

      # Container teilt sich /nix/store + /nix/var/nix/db read-only mit dem
      # Host (Standardverhalten von NixOS-Containern) — Schreibzugriffe auf
      # die Store-Datenbank MÜSSEN über den Nix-Daemon laufen, sonst schlägt
      # "big-lock" mit read-only-Fehler fehl. Root ist normalerweise "trusted"
      # und versucht sonst direkten DB-Zugriff — NIX_REMOTE erzwingt Daemon-
      # Modus auch für root (live reproduziert: nixos-rebuild switch scheiterte
      # sonst an /nix/var/nix/db/big-lock).
      environment.variables.NIX_REMOTE = "daemon";

      environment.systemPackages = with pkgs; [
        git
        python3
        curl
      ];
    };
  };

  # Host-seitige Verzeichnisse für die Testkopien. Gehören fuchs, damit rsync
  # (initiale Kopie + spätere sandbox-*-sync) ohne sudo läuft.
  systemd.tmpfiles.rules = [
    "d /var/lib/sandbox-sojus 0750 fuchs users -"
    "d /var/lib/sandbox-darwin 0750 fuchs users -"
  ];

  # sandbox-darwin nutzt denselben UID-Namespace wie der Host (kein
  # privateUsers) — der Container-sojus (uid 1000) ist dort niemand
  # Bestimmtes und hat ohne ACL keinen Zugriff auf das fuchs:users-Verzeichnis
  # (live reproduziert: "Permission denied" beim Betreten von
  # /var/lib/darwin/nixos-copy). setfacl statt chmod 0755, damit fuchs
  # weiterhin alleiniger Owner bleibt und nichts world-readable wird.
  system.activationScripts.sandboxDarwinAcl = {
    deps = [ "users" ];
    text = ''
      ${pkgs.acl}/bin/setfacl -R -m u:1000:rwx /var/lib/sandbox-darwin
      ${pkgs.acl}/bin/setfacl -R -d -m u:1000:rwx /var/lib/sandbox-darwin
    '';
  };
}
