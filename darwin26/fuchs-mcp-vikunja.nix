{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-mcp-vikunja-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-mcp-vikunja-server.py);
in {
  users.users.fuchs-mcp-vikunja = {
    isSystemUser = true;
    group        = "fuchs-mcp-vikunja";
    home         = "/var/lib/fuchs-mcp-vikunja";
    createHome   = true;
  };
  users.groups.fuchs-mcp-vikunja = {};

  systemd.services.fuchs-mcp-vikunja = {
    description = "Fuchs – Vikunja MCP Server";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-vikunja";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-vikunja";
      Group           = "fuchs-mcp-vikunja";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-vikunja.env";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 8003";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8003 ];
}
