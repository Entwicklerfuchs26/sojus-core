{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-mcp-openproject-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-mcp-openproject-server.py);
in {
  users.users.fuchs-mcp-openproject = {
    isSystemUser = true;
    group        = "fuchs-mcp-openproject";
    home         = "/var/lib/fuchs-mcp-openproject";
    createHome   = true;
  };
  users.groups.fuchs-mcp-openproject = {};

  systemd.services.fuchs-mcp-openproject = {
    description = "Fuchs – OpenProject MCP Server";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-openproject";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-openproject";
      Group           = "fuchs-mcp-openproject";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-openproject.env";
      # Phase 2: interner Port 18002, mcp-approval-proxy uebernimmt extern 8002.
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 18002";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };
}
