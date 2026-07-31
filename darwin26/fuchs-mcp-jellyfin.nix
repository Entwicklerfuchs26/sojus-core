{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-mcp-jellyfin-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-mcp-jellyfin-server.py);
in {
  users.users.fuchs-mcp-jellyfin = {
    isSystemUser = true;
    group        = "fuchs-mcp-jellyfin";
    home         = "/var/lib/fuchs-mcp-jellyfin";
    createHome   = true;
  };
  users.groups.fuchs-mcp-jellyfin = {};

  systemd.services.fuchs-mcp-jellyfin = {
    description = "Fuchs – Jellyfin MCP Server";
    after       = [ "network-online.target" "jellyfin.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-jellyfin";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-jellyfin";
      Group           = "fuchs-mcp-jellyfin";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-jellyfin.env";
      # Phase 2: interner Port 18006, mcp-approval-proxy uebernimmt extern 8006.
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 18006";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };
}
