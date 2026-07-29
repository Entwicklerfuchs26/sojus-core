{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "fuchs-shell-server.py"
    (builtins.readFile ../scripts/nexus/fuchs-shell-server.py);
  port = 8012;
in {
  # Läuft als 'sojus' (definiert in modules/ai/sojus.nix), NICHT als 'fuchs' —
  # eigenes, unprivilegiertes Home statt Zugriff auf Jonas' echtes Home
  # (SSH-Keys, Repo mit Push-Rechten etc.). sojus hat bereits eine eng
  # gewhitelistete NOPASSWD-Sudoers-Regel für genau diesen Service, siehe
  # /etc/nixos/nixos-config/modules/ai/sojus.nix.
  systemd.services.fuchs-shell = {
    description = "Fuchs Shell — MCP Shell-Zugriff auf Nexus (Port ${toString port}, User sojus)";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/sojus";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "sojus";
      Group      = "sojus";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${script} --transport streamable-http --host 192.168.1.40 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };
}
