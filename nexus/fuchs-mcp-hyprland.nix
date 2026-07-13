{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "mcp-hyprland.py" (builtins.readFile ../scripts/nexus/mcp-hyprland.py);
  port   = 9001;

  # Wrapper findet HYPRLAND_INSTANCE_SIGNATURE dynamisch aus /run/user/1000/hypr/
  startScript = pkgs.writeShellScript "start-fuchs-mcp-hyprland" ''
    SIG=$(ls /run/user/1000/hypr/ 2>/dev/null | head -1)
    if [ -n "$SIG" ]; then
      export HYPRLAND_INSTANCE_SIGNATURE="$SIG"
    fi
    exec ${pkgs.uv}/bin/uvx fastmcp run ${script} \
      --transport streamable-http --host 127.0.0.1 --port ${toString port}
  '';
in {
  systemd.services.fuchs-mcp-hyprland = {
    description = "Fuchs – Hyprland MCP (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" "graphical-session.target" ];

    environment = {
      HOME            = "/home/fuchs";
      XDG_RUNTIME_DIR = "/run/user/1000";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${startScript}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
