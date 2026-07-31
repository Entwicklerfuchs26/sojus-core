{ config, pkgs, lib, ... }:

let
  # scripts/shared/mcp_approval_proxy.py importiert mcp_risk_classifier als
  # Sibling-Modul — beide müssen im selben Verzeichnis landen (gleiches Muster
  # wie nexus/fuchs-shell.nix und darwin26/mcp-approval-service.nix).
  srcDir = pkgs.runCommand "mcp-approval-proxy-src" {} ''
    mkdir -p $out
    cp ${pkgs.writeText "mcp_approval_proxy.py" (builtins.readFile ../scripts/shared/mcp_approval_proxy.py)} $out/mcp_approval_proxy.py
    cp ${pkgs.writeText "mcp_risk_classifier.py" (builtins.readFile ../scripts/shared/mcp_risk_classifier.py)} $out/mcp_risk_classifier.py
  '';
  toolTiers = pkgs.writeText "tool_tiers.json" (builtins.readFile ../config/tool_tiers.json);

  # Phase 2 (docs/mcp-approval-architecture.md): Server für Server migriert,
  # nicht alles auf einmal. Pilot (fuchs-anilist) zuerst einzeln deployt und
  # verifiziert, jetzt Rest der darwin26-Flotte im zweiten Batch.
  # Interner Port = externer Port + 10000, feste Konvention für den ganzen Umbau.
  servers = [
    { name = "nc-weites-feld";       external_port = 8000; internal_port = 18000; }
    { name = "nc-weites-feld-extra"; external_port = 8001; internal_port = 18001; }
    { name = "fuchs-openproject";    external_port = 8002; internal_port = 18002; }
    { name = "fuchs-vikunja";        external_port = 8003; internal_port = 18003; }
    { name = "fuchs-homeassistant";  external_port = 8004; internal_port = 18004; }
    { name = "fuchs-n8n";            external_port = 8005; internal_port = 18005; }
    { name = "fuchs-jellyfin";       external_port = 8006; internal_port = 18006; }
    { name = "fuchs-immich";         external_port = 8007; internal_port = 18007; }
    { name = "fuchs-anilist";        external_port = 8008; internal_port = 18008; }
    { name = "nc-sternenhof";        external_port = 8009; internal_port = 18009; }
  ];

  proxyConfig = pkgs.writeText "mcp-approval-proxy.json" (builtins.toJSON { inherit servers; });

  # Muss mit approvalApiToken in mcp-approval-service.nix identisch sein.
  approvalApiToken = "mcp-approval-internal-token-change-in-prod";
in {
  users.users.mcp-approval-proxy = {
    isSystemUser = true;
    group        = "mcp-approval-proxy";
    home         = "/var/lib/mcp-approval-proxy";
    createHome   = true;
  };
  users.groups.mcp-approval-proxy = {};

  systemd.services.mcp-approval-proxy = {
    description = "MCP Approval Proxy — Tier-Gate vor der MCP-Flotte (Phase 2, ${toString (builtins.length servers)} Server)";
    after       = [ "network-online.target" "mcp-approval-service.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/mcp-approval-proxy";
      UV_CACHE_DIR         = "/var/lib/mcp-approval-proxy/.cache/uv";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";

      MCP_PROXY_HOST       = "darwin26";
      MCP_PROXY_CONFIG     = "${proxyConfig}";
      TOOL_TIERS_FILE      = "${toolTiers}";
      APPROVAL_URL          = "http://127.0.0.1:8014";
      APPROVAL_API_TOKEN    = approvalApiToken;
      APPROVAL_WAIT_TIMEOUT = "90";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "mcp-approval-proxy";
      Group           = "mcp-approval-proxy";
      ExecStart       = "${pkgs.uv}/bin/uv run --python ${pkgs.python3}/bin/python3 --with aiohttp ${srcDir}/mcp_approval_proxy.py";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ "/var/lib/mcp-approval-proxy" ];
    };
  };

  # Übernimmt die externen Ports der migrierten Server — die echten Server
  # binden jetzt auf interne Ports ohne eigene Firewall-Freigabe.
  networking.firewall.allowedTCPPorts = map (s: s.external_port) servers;
}
