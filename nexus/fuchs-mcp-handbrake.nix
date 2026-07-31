{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-handbrake.py" (builtins.readFile ../scripts/nexus/mcp-handbrake.py);
  # Phase 2: interner Port 19009, mcp-approval-proxy uebernimmt extern 9009.
  port   = 19009;
in {
  systemd.services.fuchs-mcp-handbrake = {
    description = "Fuchs – HandBrake Video-Encode MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    # HandBrakeCLI via NixOS path-Attribut (statt environment.PATH, das kollidiert)
    path = [ pkgs.handbrake ];

    environment = {
      HOME = "/home/fuchs";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 127.0.0.1 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "5s";
    };
  };
}
