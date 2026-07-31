{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-libreoffice.py" (builtins.readFile ../scripts/nexus/mcp-libreoffice.py);
  # Phase 2: interner Port 19004, mcp-approval-proxy uebernimmt extern 9004.
  port   = 19004;
in {
  systemd.services.fuchs-mcp-libreoffice = {
    description = "Fuchs – LibreOffice MCP (HTTP, Port ${toString port})";
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
