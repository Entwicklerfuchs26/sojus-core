{ config, pkgs, lib, ... }:

let
  # Phase 2: interner Port 19000, mcp-approval-proxy uebernimmt extern 9000.
  # 127.0.0.1 statt 192.168.1.40 — Backend nur noch lokal erreichbar, kein
  # Umweg ueber die Firewall-INPUT-Chain fuer die eigene LAN-IP noetig.
  port = 19000;
  # SICHERHEIT: Ausschließlich /home/fuchs — kein /etc/nixos, kein /
  allowedDir = "/home/fuchs";

  # Wrapper-Script: gibt mcp-proxy einen sauberen Single-Arg-Befehl
  # (systemd ExecStart zerlegt quoted strings nicht zuverlässig in einem arg)
  startScript = pkgs.writeShellScript "run-filesystem-mcp" ''
    exec ${pkgs.nodejs}/bin/npx -y @modelcontextprotocol/server-filesystem ${allowedDir}
  '';
in {
  systemd.services.fuchs-mcp-filesystem = {
    description = "Sojus – Dateisystem MCP (read-only für sojus, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    path = [ pkgs.bash pkgs.nodejs ];

    environment = {
      HOME             = "/home/sojus";
      NPM_CONFIG_CACHE = "/home/sojus/.npm";
      UV_CACHE_DIR     = "/home/sojus/.cache/uv";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "sojus";
      # URL-Pfad: /servers/filesystem/mcp (nicht /mcp — mcp-proxy 0.12.0 named-server routing)
      # Versionspin: mcp-proxy 0.12.0 + mcp>=2.0.0 bricht mit
      # "ImportError: cannot import name 'request_ctx' from mcp.server.lowlevel.server"
      # (PyPI-Versionsdrift, ohne Pin holt uvx sonst das neueste mcp). Getestet
      # gegen einen echten Named-Server vor dem Deploy.
      ExecStart  = ''${pkgs.uv}/bin/uvx --with "mcp<2.0.0" mcp-proxy==0.12.0 \
        --port ${toString port} --host 127.0.0.1 \
        --transport streamablehttp \
        --named-server filesystem ${startScript}'';
      Restart    = "on-failure";
      RestartSec = "5s";
    };
  };
}
