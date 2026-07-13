{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-lightburn.py" (builtins.readFile ../scripts/nexus/mcp-lightburn.py);
  port   = 9010;
in {
  systemd.services.fuchs-mcp-lightburn = {
    description = "Fuchs – LightBurn Laser-CAD MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
      # lightburn binary muss im PATH sein (aus dem NixOS-Paket)
      PATH = "/run/current-system/sw/bin:/run/wrappers/bin";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 192.168.1.40 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
