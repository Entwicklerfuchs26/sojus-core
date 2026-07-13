{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-mcp-immich-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-mcp-immich-server.py);
in {
  users.users.fuchs-mcp-immich = {
    isSystemUser = true;
    group        = "fuchs-mcp-immich";
    home         = "/var/lib/fuchs-mcp-immich";
    createHome   = true;
  };
  users.groups.fuchs-mcp-immich = {};

  systemd.services.fuchs-mcp-immich = {
    description = "Fuchs – Immich MCP Server";
    after       = [ "network-online.target" "immich-server.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-immich";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-immich";
      Group           = "fuchs-mcp-immich";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-immich.env";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 8007";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8007 ];
}
