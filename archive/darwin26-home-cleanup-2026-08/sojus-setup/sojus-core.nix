{ config, pkgs, lib, ... }:

{
  # ── SOJUS CORE (Port 3001 — OpenAI-kompatibler Endpunkt) ─────────────────────

  users.users.sojus-core = {
    isSystemUser = true;
    group        = "sojus-core";
    home         = "/var/lib/sojus-core";
    createHome   = true;
  };
  users.groups.sojus-core = {};

  systemd.services.sojus-core = {
    description = "Sojus Core — KI-Agent mit MCP-Tools";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/sojus-core";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      UV_CACHE_DIR         = "/var/lib/sojus-core/.cache/uv";
      LD_LIBRARY_PATH      = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
        pkgs.openssl.out
        pkgs.glib
      ];
      # Pfade zu Datendateien
      MEMORY_FILE     = "/etc/sojus/memory.json";
      REMINDERS_FILE  = "/etc/sojus/reminders.json";
      TOOL_GROUPS_FILE = "/etc/sojus/tool_groups.json";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "sojus-core";
      Group           = "sojus-core";
      EnvironmentFile = "/etc/sojus/config.env";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with fastapi --with httpx --with anthropic uvicorn core:app --host 0.0.0.0 --port 3001";
      WorkingDirectory = "/etc/sojus";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      # Schreibzugriff auf /etc/sojus/ für memory.json und reminders.json
      ReadWritePaths  = [ "/etc/sojus" ];
    };
  };

  # ── SOJUS MEMORY MCP SERVER (Port 8010) ──────────────────────────────────────

  systemd.services.fuchs-sojus-memory = {
    description = "Sojus Memory MCP Server — Langzeitgedächtnis";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/sojus-core";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      UV_CACHE_DIR         = "/var/lib/sojus-core/.cache/uv";
      LD_LIBRARY_PATH      = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
        pkgs.openssl.out
        pkgs.glib
      ];
      MEMORY_FILE = "/etc/sojus/memory.json";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "sojus-core";
      Group           = "sojus-core";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with fastmcp fastmcp run /etc/sojus/memory_mcp.py --transport streamable-http --host 0.0.0.0 --port 8010";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ "/etc/sojus" ];
    };
  };

  networking.firewall.allowedTCPPorts = [ 3001 8010 ];
}
