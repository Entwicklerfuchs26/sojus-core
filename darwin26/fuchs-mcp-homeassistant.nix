{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-mcp-homeassistant-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-mcp-homeassistant-server.py);
in {
  users.users.fuchs-mcp-homeassistant = {
    isSystemUser = true;
    group        = "fuchs-mcp-homeassistant";
    home         = "/var/lib/fuchs-mcp-homeassistant";
    createHome   = true;
  };
  users.groups.fuchs-mcp-homeassistant = {};

  systemd.services.fuchs-mcp-homeassistant = {
    description = "Fuchs – Home Assistant MCP Server";
    after       = [ "network-online.target" "home-assistant.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-homeassistant";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-homeassistant";
      Group           = "fuchs-mcp-homeassistant";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-homeassistant.env";
      # Phase 2: interner Port 18004, mcp-approval-proxy uebernimmt extern 8004.
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 18004";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };
}
