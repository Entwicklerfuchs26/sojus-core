{ config, pkgs, lib, ... }:

let
  port = 9005;
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
        --port ${toString port} --host 0.0.0.0 \
        --transport streamablehttp \
        --named-server freecad "${pkgs.uv}/bin/uvx freecad-mcp"'';
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
