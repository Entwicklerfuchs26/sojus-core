{ config, pkgs, lib, ... }:

let
  srcDir = pkgs.runCommand "mcp-approval-proxy-src" {} ''
    mkdir -p $out
    cp ${pkgs.writeText "mcp_approval_proxy.py" (builtins.readFile ../scripts/shared/mcp_approval_proxy.py)} $out/mcp_approval_proxy.py
    cp ${pkgs.writeText "mcp_risk_classifier.py" (builtins.readFile ../scripts/shared/mcp_risk_classifier.py)} $out/mcp_risk_classifier.py
  '';
  toolTiers = pkgs.writeText "tool_tiers.json" (builtins.readFile ../config/tool_tiers.json);

  # fuchs-shell (Port 8012) ist bewusst NICHT dabei: hat aus Phase 1 schon
  # eigenes Tier-Gate direkt im Server (scripts/nexus/fuchs-shell-server.py),
  # spricht mcp-approval-service bereits selbst an. Nochmal davor waere
  # doppeltes Gating fuer denselben Aufruf. Phase 2 deckt hier den Rest der
  # Flotte ab, die bisher komplett ungeprueft lief.
  servers = [
    { name = "fuchs-filesystem"; external_port = 9000; internal_port = 19000; }
    { name = "fuchs-hyprland";   external_port = 9001; internal_port = 19001; }
    { name = "fuchs-vivaldi";    external_port = 9002; internal_port = 19002; }
    { name = "fuchs-obs";        external_port = 9003; internal_port = 19003; }
    { name = "fuchs-libreoffice";external_port = 9004; internal_port = 19004; }
    { name = "fuchs-freecad";    external_port = 9005; internal_port = 19005; }
    { name = "fuchs-davinci";    external_port = 9006; internal_port = 19006; }
    { name = "fuchs-blender";    external_port = 9007; internal_port = 19007; }
    { name = "fuchs-stellarium"; external_port = 9008; internal_port = 19008; }
    { name = "fuchs-handbrake";  external_port = 9009; internal_port = 19009; }
    { name = "fuchs-lightburn";  external_port = 9010; internal_port = 19010; }
    { name = "fuchs-darktable";  external_port = 9011; internal_port = 19011; }
  ];

  proxyConfig = pkgs.writeText "mcp-approval-proxy.json" (builtins.toJSON { inherit servers; });

  # Muss mit approvalApiToken in darwin26/mcp-approval-service.nix identisch sein.
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
    description = "MCP Approval Proxy — Tier-Gate vor der nexus-MCP-Flotte (Phase 2, ${toString (builtins.length servers)} Server, ohne fuchs-shell)";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME                 = "/var/lib/mcp-approval-proxy";
      UV_CACHE_DIR         = "/var/lib/mcp-approval-proxy/.cache/uv";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";

      MCP_PROXY_HOST       = "nexus";
      MCP_PROXY_CONFIG     = "${proxyConfig}";
      TOOL_TIERS_FILE      = "${toolTiers}";
      # mcp-approval-service laeuft auf darwin26 (gleiche Adresse wie in fuchs-shell.nix).
      APPROVAL_URL          = "http://192.168.1.26:8014";
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

  # Kein Firewall-Zusatz noetig: die externen Ports 9000-9011 sind schon
  # ueber die mcp-sojus-filter-Chain in default.nix offen (darwin26 + nexus
  # selbst) — der Proxy uebernimmt einfach dieselben Portnummern, die vorher
  # die einzelnen Server direkt belegt haben.
}
