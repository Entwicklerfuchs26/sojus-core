{ config, pkgs, lib, ... }:

let
  port = 9007;
in {
  systemd.services.fuchs-mcp-blender = {
    description = "Fuchs – Blender 3D MCP via mcp-proxy (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = ''${pkgs.uv}/bin/uvx mcp-proxy \
        --port ${toString port} --host 192.168.1.40 \
        --transport streamablehttp \
        --named-server blender "${pkgs.uv}/bin/uvx blender-mcp"'';
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
