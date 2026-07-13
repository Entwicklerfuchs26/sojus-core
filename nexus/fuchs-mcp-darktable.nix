{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-darktable.py" (builtins.readFile ../scripts/nexus/mcp-darktable.py);
  port   = 9011;
in {
  systemd.services.fuchs-mcp-darktable = {
    description = "Fuchs – Darktable Foto-Workflow MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
      # darktable-cli für Export; sqlite3 via CPython stdlib
      PATH = "/run/current-system/sw/bin:/run/wrappers/bin";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "5s";
    };
  };
}
