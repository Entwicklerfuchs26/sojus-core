{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-lightburn.py" (builtins.readFile ../scripts/nexus/mcp-lightburn.py);
  # Phase 2: interner Port 19010, mcp-approval-proxy uebernimmt extern 9010.
  port   = 19010;
in {
  systemd.services.fuchs-mcp-lightburn = {
    description = "Fuchs – LightBurn Laser-CAD MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    # lightburn ist proprietär/unfree und nicht über pkgs verfügbar →
    # kein path-Attribut; lightburn_open() gibt graceful error wenn Binary fehlt.

    environment = {
      HOME = "/home/fuchs";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 127.0.0.1 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
