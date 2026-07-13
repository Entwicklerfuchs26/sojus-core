{ config, pkgs, lib, ... }:

let
  port = 9000;
  # Erlaubte Verzeichnisse — identisch zu .claude.json stdio-Konfiguration
  allowedDirs = "/home/fuchs /etc/nixos /";
in {
  systemd.services.fuchs-mcp-filesystem = {
    description = "Fuchs – Dateisystem MCP via mcp-proxy (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME     = "/home/fuchs";
      NPM_CONFIG_CACHE = "/home/fuchs/.npm";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      # mcp-proxy bridgt stdio→HTTP; --named-server definiert den stdio-Sub-Prozess
      ExecStart  = ''${pkgs.uv}/bin/uvx mcp-proxy \
        --port ${toString port} --host 0.0.0.0 \
        --transport streamablehttp \
        --named-server filesystem \
          "${pkgs.nodejs}/bin/npx -y @modelcontextprotocol/server-filesystem ${allowedDirs}"'';
      Restart    = "on-failure";
      RestartSec = "5s";
    };
  };
}
