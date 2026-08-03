{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "fuchs-sandbox-control-nexus-server.py"
    (builtins.readFile ../scripts/nexus/fuchs-sandbox-control-nexus-server.py);

  port = 9012;

  # Muss mit approvalApiToken in darwin26/mcp-approval-service.nix und
  # nexus/fuchs-shell.nix identisch sein.
  approvalApiToken = "mcp-approval-internal-token-change-in-prod";

  # Kein --delete: /etc/nixos/nixos-config ist die echte Produktivconfig des
  # Hosts, nicht nur ein Testrepo. Eine veraltete/unvollständige Testkopie
  # soll niemals Dateien aus der echten Config LÖSCHEN können — nur
  # überschreiben/ergänzen (gleiche Begründung wie sandbox-darwin-sync auf
  # darwin26). Rückgängig machen geht per git in nixos-config.
  syncScript = pkgs.writeShellScript "sandbox-nexus-sync" ''
    #!/usr/bin/env bash
    set -euo pipefail
    SRC="/var/lib/sandbox-nexus/nixos-config-copy/"
    DST="/etc/nixos/nixos-config/"
    rsync -a --exclude='.git' "$SRC" "$DST"
    echo "sandbox-nexus sync: $SRC -> $DST OK"
  '';

  syncScriptPath = "/home/sojus/bin/sandbox-nexus-sync.sh";
in {
  systemd.services.fuchs-sandbox-control-nexus = {
    description = "Fuchs Sandbox Control (Nexus) — MCP-Steuerung für sandbox-nexus-Container (Port ${toString port}, User sojus)";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    # sudo liegt als setuid-Wrapper unter /run/wrappers/bin, NICHT im
    # Nix-Store — Systemd-Units bekommen sonst keinerlei PATH,
    # subprocess.run(["sudo", ...]) würde sonst mit "No such file or
    # directory" scheitern (auf darwin26 live reproduziert).
    path = [ "/run/wrappers" ];

    environment = {
      HOME                  = "/home/sojus";
      UV_PYTHON             = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE  = "only-system";
      UV_CACHE_DIR          = "/home/sojus/.cache/uv";
      SYNC_SCRIPT            = syncScriptPath;
      APPROVAL_URL           = "http://192.168.1.26:8014";
      APPROVAL_API_TOKEN     = approvalApiToken;
      APPROVAL_WAIT_TIMEOUT  = "90";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "sojus";
      Group      = "sojus";
      ExecStart  = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 fastmcp run ${script} --transport streamable-http --host 192.168.1.40 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
      # KEIN NoNewPrivileges — dieser Service MUSS per sudo eskalieren
      # (systemctl start/stop/status auf den Container, das Sync-Skript).
      # NoNewPrivileges blockiert sudo komplett auf Kernel-Ebene, unabhängig
      # von sudoers (auf darwin26 live reproduziert: "The 'no new
      # privileges' flag is set").
    };
  };

  # Fixer Pfad statt Nix-Store-Hash, damit die sudoers-Regel in
  # modules/ai/sojus.nix nicht bei jeder Skript-Änderung bricht.
  system.activationScripts.sandboxNexusSyncScript = {
    deps = [ "users" ];
    text = ''
      install -d -m 750 -o sojus -g sojus /home/sojus/bin
      install -m 750 ${syncScript} ${syncScriptPath}
    '';
  };
}
