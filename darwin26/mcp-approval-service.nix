{ config, pkgs, lib, ... }:

let
  scriptDir = pkgs.writeTextDir "approval_service.py"
    (builtins.readFile ../scripts/darwin26/approval_service.py);
  port = 8014;

  # MVP-Token nach hermesApiKey-Vorbild (siehe hermes.nix) — für Produktion
  # ersetzen (Entscheidung siehe docs/mcp-approval-architecture.md, Frage #1).
  # Muss mit dem Token in nexus/fuchs-shell.nix identisch sein.
  approvalApiToken = "mcp-approval-internal-token-change-in-prod";
in {
  users.users.mcp-approval = {
    isSystemUser = true;
    group        = "mcp-approval";
    home         = "/var/lib/mcp-approval";
    createHome   = true;
  };
  users.groups.mcp-approval = {};

  systemd.services.mcp-approval-service = {
    description = "MCP Approval Service — zentrale Freigabe-Warteschlange für Tier-3 Tool-Aufrufe";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      # Ohne HOME kann uvx seinen Cache nicht anlegen und bricht sofort mit
      # exit code 2 ab ("Failed to initialize cache") — lokal reproduziert.
      HOME         = "/var/lib/mcp-approval";
      UV_CACHE_DIR = "/var/lib/mcp-approval/.cache/uv";

      APPROVAL_API_TOKEN   = approvalApiToken;
      APPROVAL_DB_PATH     = "/var/lib/mcp-approval/approvals.db";
      APPROVAL_TTL_SECONDS = "300";
      # Home Assistant läuft auf demselben Host — Push ist optional:
      # HA_TOKEN bewusst leer, ohne echten Long-Lived-Token bleibt es beim Log.
      HA_URL   = "http://127.0.0.1:8123";
      HA_TOKEN = "";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "mcp-approval";
      Group           = "mcp-approval";
      ExecStart       = "${pkgs.uv}/bin/uvx --with fastapi --with 'uvicorn[standard]' uvicorn approval_service:app --app-dir ${scriptDir} --host 0.0.0.0 --port ${toString port}";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ "/var/lib/mcp-approval" ];
    };
  };

  # Kein IP-Filter wie bei nexus' mcp-sojus-filter-Chain — gleiches Muster wie
  # hermes-agent (Port 3002): Bearer-Token ist der eigentliche Schutz, siehe
  # docs/mcp-approval-architecture.md.
  networking.firewall.allowedTCPPorts = [ port ];
}
