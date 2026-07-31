{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-mcp-n8n-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-mcp-n8n-server.py);
in {
  users.users.fuchs-mcp-n8n = {
    isSystemUser = true;
    group        = "fuchs-mcp-n8n";
    home         = "/var/lib/fuchs-mcp-n8n";
    createHome   = true;
  };
  users.groups.fuchs-mcp-n8n = {};

  systemd.services.fuchs-mcp-n8n = {
    description = "Fuchs – n8n MCP Server";
    after       = [ "network-online.target" "n8n.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-n8n";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-n8n";
      Group           = "fuchs-mcp-n8n";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-n8n.env";
      # Phase 2: interner Port 18005, mcp-approval-proxy uebernimmt extern 8005.
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 18005";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };
}
