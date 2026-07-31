{ config, pkgs, lib, ... }:

let
  # Phase 2: interner Port 19003, mcp-approval-proxy uebernimmt extern 9003.
  port = 19003;
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
      # Versionspin: mcp-proxy 0.12.0 + mcp>=2.0.0 bricht mit
      # "ImportError: cannot import name 'request_ctx' from mcp.server.lowlevel.server"
      # (PyPI-Versionsdrift, ohne Pin holt uvx sonst das neueste mcp).
      ExecStart       = ''${pkgs.uv}/bin/uvx --with "mcp<2.0.0" mcp-proxy==0.12.0 \
        --port ${toString port} --host 127.0.0.1 \
        --transport streamablehttp \
        --pass-environment \
        --named-server obs "${pkgs.nodejs}/bin/npx -y obs-mcp@latest"'';
      Restart         = "on-failure";
      RestartSec      = "10s";
    };
  };
}
