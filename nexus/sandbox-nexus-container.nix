{ config, pkgs, lib, ... }:

{
  # Sandbox-Container für Nexus-Systemebene: isolierte Kopie von
  # /etc/nixos/nixos-config zum Testen von NixOS-Modulen inkl. echtem
  # nixos-rebuild switch, ohne den echten Host anzufassen. Gleiches Muster
  # wie sandbox-darwin auf darwin26 (sojus-core/darwin26/containers.nix).
  # sojus-core wird read-only mit reingemountet, weil flake.nix es als
  # path:-Flake-Input referenziert (sonst evaluiert die Kopie nicht).
  containers.sandbox-nexus = {
    autoStart = false;
    privateNetwork = true;
    hostAddress = "10.10.3.1";
    localAddress = "10.10.3.2";

    bindMounts = {
      "/var/lib/nexus" = {
        hostPath = "/var/lib/sandbox-nexus";
        isReadOnly = false;
      };
      "/home/fuchs/sojus-core" = {
        hostPath = "/home/fuchs/sojus-core";
        isReadOnly = true;
      };
    };

    config = { config, pkgs, ... }: {
      system.stateVersion = "25.11";

      # Normaler User mit passwortlosem wheel-sudo NUR innerhalb des
      # Containers — der Container selbst ist die Isolationsgrenze.
      # uid/gid fest auf 29000 (statt auto-vergeben oder 1000!), damit die
      # ACL auf dem Host-Verzeichnis stabil bleibt. uid 1000 kollidiert auf
      # Nexus mit dem echten Host-User "fuchs" — 29000 liegt fernab davon
      # (gleicher Fund/Fix wie bei sandbox-darwin auf darwin26, wo uid 1000
      # mit "mattis" kollidierte).
      users.users.sojus = {
        isNormalUser = true;
        uid = 29000;
        group = "sojus";
        home = "/var/lib/sojus";
        createHome = true;
        extraGroups = [ "wheel" ];
      };
      users.groups.sojus.gid = 29000;
      security.sudo.wheelNeedsPassword = false;

      # Container teilt sich /nix/store + /nix/var/nix/db read-only mit dem
      # Host (Standardverhalten von NixOS-Containern) — Schreibzugriffe auf
      # die Store-Datenbank MÜSSEN über den Nix-Daemon laufen, sonst
      # scheitert nixos-rebuild switch an /nix/var/nix/db/big-lock
      # (read-only). environment.variables propagiert das bei Containern
      # nicht zuverlässig in /etc/set-environment (live auf darwin26
      # reproduziert) — deshalb hier über /etc/profile.d + explizites
      # env_keep für sudo, damit "sudo NIX_REMOTE=daemon nixos-rebuild
      # switch" (oder einfach "sudo nixos-rebuild switch" nach Login) sicher
      # durchkommt.
      environment.etc."profile.d/nix-remote.sh".text = ''
        export NIX_REMOTE=daemon
      '';
      security.sudo.extraConfig = ''
        Defaults env_keep += "NIX_REMOTE"
      '';

      nix.settings.experimental-features = [ "nix-command" "flakes" ];

      environment.systemPackages = with pkgs; [
        git
        python3
        curl
      ];
    };
  };

  # Host-seitiges Verzeichnis für die Testkopie. Gehört fuchs, damit rsync
  # (initiale Kopie + spätere sandbox-nexus-sync) ohne sudo läuft.
  systemd.tmpfiles.rules = [
    "d /var/lib/sandbox-nexus 0750 fuchs users -"
  ];

  # ACL für den Container-sojus (uid 29000) — Container teilt UID-Namespace
  # mit dem Host (kein privateUsers), ohne ACL "Permission denied" beim
  # Betreten von /var/lib/nexus/nixos-config-copy. mkdir -p hier statt nur
  # per systemd.tmpfiles.rules: Reihenfolge zwischen tmpfiles und
  # activationScripts ist nicht garantiert — beim allerersten Rebuild
  # existierte das Verzeichnis noch nicht, setfacl scheiterte mit "Datei
  # oder Verzeichnis nicht gefunden" (live auf Nexus reproduziert).
  system.activationScripts.sandboxNexusAcl = {
    deps = [ "users" ];
    text = ''
      mkdir -p /var/lib/sandbox-nexus
      ${pkgs.acl}/bin/setfacl -R -m u:29000:rwx /var/lib/sandbox-nexus
      ${pkgs.acl}/bin/setfacl -R -d -m u:29000:rwx /var/lib/sandbox-nexus
    '';
  };
}
