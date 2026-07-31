{ config, pkgs, lib, ... }:

let
  # Phase 2: interner Port 19005, mcp-approval-proxy uebernimmt extern 9005.
  port = 19005;
in {
  systemd.services.fuchs-mcp-freecad = {
    description = "Fuchs – FreeCAD MCP via mcp-proxy (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = ''${pkgs.uv}/bin/uvx mcp-proxy \
        --port ${toString port} --host 127.0.0.1 \
        --transport streamablehttp \
        --named-server freecad "${pkgs.uv}/bin/uvx freecad-mcp"'';
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
