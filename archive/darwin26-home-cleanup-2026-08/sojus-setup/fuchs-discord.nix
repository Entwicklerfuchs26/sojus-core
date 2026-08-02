{ config, pkgs, lib, ... }:

{
  users.users.fuchs-discord = {
    isSystemUser = true;
    group        = "fuchs-discord";
    home         = "/var/lib/fuchs-discord";
    createHome   = true;
  };
  users.groups.fuchs-discord = {};

  systemd.services.fuchs-discord = {
    description = "Fuchs – Discord Bot + MCP Server";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-discord";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      UV_CACHE_DIR         = "/var/lib/fuchs-discord/.cache/uv";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
        pkgs.openssl.out
        pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-discord";
      Group           = "fuchs-discord";
      EnvironmentFile = "/etc/sojus/fuchs-discord.env";
      ExecStart       = "${pkgs.uv}/bin/uv run --python ${pkgs.python3}/bin/python3 --with 'discord.py' --with fastmcp --with httpx /etc/sojus/fuchs-discord-server.py";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  # Nur lokal erreichbar (Sojus-Core auf 127.0.0.1) — kein öffentlicher Port nötig
  # Falls Nexus zugreifen muss: 8011 in allowedTCPPorts eintragen
  # networking.firewall.allowedTCPPorts = [ 8011 ];
}
