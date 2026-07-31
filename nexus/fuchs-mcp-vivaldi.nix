{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-vivaldi.py" (builtins.readFile ../scripts/nexus/mcp-vivaldi.py);
  # Phase 2: interner Port 19002, mcp-approval-proxy uebernimmt extern 9002.
  port   = 19002;
in {
  systemd.services.fuchs-mcp-vivaldi = {
    description = "Fuchs – Vivaldi Browser MCP via CDP (HTTP, Port ${toString port})";
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
