{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-stellarium.py" (builtins.readFile ../scripts/nexus/mcp-stellarium.py);
  port   = 9008;
in {
  systemd.services.fuchs-mcp-stellarium = {
    description = "Fuchs – Stellarium MCP via RemoteControl API (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
