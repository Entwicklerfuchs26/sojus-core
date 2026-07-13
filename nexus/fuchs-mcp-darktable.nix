{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-darktable.py" (builtins.readFile ../scripts/nexus/mcp-darktable.py);
  port   = 9011;
in {
  systemd.services.fuchs-mcp-darktable = {
    description = "Fuchs – Darktable Foto-Workflow MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    # darktable-cli via NixOS path-Attribut (statt environment.PATH, das kollidiert)
    path = [ pkgs.darktable ];

    environment = {
      HOME = "/home/fuchs";
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
