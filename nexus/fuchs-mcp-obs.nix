{ config, pkgs, lib, ... }:

let
  port = 9003;
in {
  # agenix Secret: OBS WebSocket Passwort
  age.secrets.fuchs-mcp-obs-env = {
    file  = ../secrets/fuchs-mcp-obs-env.age;
    owner = "fuchs";
    group = "users";
    mode  = "0400";
  };

  systemd.services.fuchs-mcp-obs = {
    description = "Fuchs – OBS Studio MCP via mcp-proxy (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    # npx spawns `sh` and `node` internally → both must be in PATH
    path = [ pkgs.bash pkgs.nodejs ];

    environment = {
      HOME             = "/home/fuchs";
      NPM_CONFIG_CACHE = "/home/fuchs/.npm";
      OBS_WEBSOCKET_URL = "ws://localhost:4455";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs";
      EnvironmentFile = config.age.secrets.fuchs-mcp-obs-env.path;
      ExecStart       = ''${pkgs.uv}/bin/uvx mcp-proxy \
        --port ${toString port} --host 192.168.1.40 \
        --transport streamablehttp \
        --pass-environment \
        --named-server obs "${pkgs.nodejs}/bin/npx -y obs-mcp@latest"'';
      Restart         = "on-failure";
      RestartSec      = "10s";
    };
  };
}
