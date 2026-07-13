{ config, pkgs, lib, ... }:

let
  port = 9003;
in {
  systemd.services.fuchs-mcp-obs = {
    description = "Fuchs – OBS Studio MCP via mcp-proxy (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME             = "/home/fuchs";
      NPM_CONFIG_CACHE = "/home/fuchs/.npm";
      OBS_WEBSOCKET_URL = "ws://localhost:4455";
      # OBS_WEBSOCKET_PASSWORD: via EnvironmentFile (Secret, nicht in Git)
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs";
      EnvironmentFile = "/etc/sojus/nexus/fuchs-mcp-obs.env";
      ExecStart       = ''${pkgs.uv}/bin/uvx mcp-proxy \
        --port ${toString port} --host 0.0.0.0 \
        --transport streamablehttp \
        --pass-environment \
        --named-server obs "${pkgs.nodejs}/bin/npx -y obs-mcp@latest"'';
      Restart         = "on-failure";
      RestartSec      = "10s";
    };
  };
}
