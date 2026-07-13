{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-handbrake.py" (builtins.readFile ../scripts/nexus/mcp-handbrake.py);
  port   = 9009;
in {
  systemd.services.fuchs-mcp-handbrake = {
    description = "Fuchs – HandBrake Video-Encode MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
      # HandBrakeCLI muss im PATH sein
      PATH = "/run/current-system/sw/bin:/run/wrappers/bin";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 192.168.1.40 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "5s";
    };
  };
}
