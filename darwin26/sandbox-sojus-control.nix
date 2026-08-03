{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "sandbox-sojus-control-server.py"
    (builtins.readFile ../scripts/darwin26/sandbox-sojus-control-server.py);

  port = 8015;

  # Muss mit approvalApiToken in darwin26/mcp-approval-service.nix identisch sein.
  approvalApiToken = "mcp-approval-internal-token-change-in-prod";

  syncScript = pkgs.writeShellScript "sandbox-sojus-sync" ''
    #!/usr/bin/env bash
    set -euo pipefail
    SRC="/var/lib/sandbox-sojus/sojus-core/"
    DST="/home/fuchs/sojus-core/"
    rsync -a --delete --exclude='.git' "$SRC" "$DST"
    chown -R fuchs:users "$DST"
    echo "sandbox-sojus sync: $SRC -> $DST OK"
  '';

  syncScriptPath = "/var/lib/sandbox-sojus-ctl/bin/sandbox-sojus-sync.sh";
in {
  users.users.sandbox-sojus-ctl = {
    isSystemUser = true;
    group        = "sandbox-sojus-ctl";
    home         = "/var/lib/sandbox-sojus-ctl";
    createHome   = true;
  };
  users.groups.sandbox-sojus-ctl = {};

  systemd.services.fuchs-sandbox-control = {
    description = "Fuchs Sandbox Control — MCP-Steuerung für sandbox-sojus-Container (Port ${toString port})";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                  = "/var/lib/sandbox-sojus-ctl";
      UV_PYTHON             = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE  = "only-system";
      UV_CACHE_DIR          = "/var/lib/sandbox-sojus-ctl/.cache/uv";
      SYNC_SCRIPT            = syncScriptPath;
      APPROVAL_URL           = "http://127.0.0.1:8014";
      APPROVAL_API_TOKEN     = approvalApiToken;
      APPROVAL_WAIT_TIMEOUT  = "90";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "sandbox-sojus-ctl";
      Group           = "sandbox-sojus-ctl";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 fastmcp run ${script} --transport streamable-http --host 127.0.0.1 --port ${toString port}";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  # Fixer Pfad statt Nix-Store-Hash, damit die sudoers-Regel unten nicht bei
  # jeder Änderung des Skripts bricht (gleiches Muster wie safe-rebuild.sh
  # in nixos-config/modules/ai/sojus.nix auf Nexus).
  system.activationScripts.sandboxSojusSyncScript = {
    deps = [ "users" ];
    text = ''
      install -d -m 750 -o sandbox-sojus-ctl -g sandbox-sojus-ctl /var/lib/sandbox-sojus-ctl/bin
      install -m 750 ${syncScript} ${syncScriptPath}
    '';
  };

  # Nur diese exakten Befehle, sonst DENY by default. Kein nixos-rebuild,
  # kein allgemeines systemctl — dieser User darf ausschließlich den
  # sandbox-sojus-Container an/aus schalten und die feste Sync-Kopie fahren.
  security.sudo.extraRules = [
    {
      users = [ "sandbox-sojus-ctl" ];
      commands = [
        { command = "/run/current-system/sw/bin/systemctl start container-sandbox-sojus";  options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl stop container-sandbox-sojus";   options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container-sandbox-sojus"; options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container-sandbox-sojus --no-pager"; options = [ "NOPASSWD" ]; }
        { command = syncScriptPath; options = [ "NOPASSWD" ]; }
      ];
    }
  ];
}
