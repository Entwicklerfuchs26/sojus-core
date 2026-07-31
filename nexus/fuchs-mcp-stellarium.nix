{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-stellarium.py" (builtins.readFile ../scripts/nexus/mcp-stellarium.py);
  # Phase 2: interner Port 19008, mcp-approval-proxy uebernimmt extern 9008.
  port   = 19008;
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
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 127.0.0.1 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
