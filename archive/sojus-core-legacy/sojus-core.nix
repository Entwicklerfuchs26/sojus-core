{ config, pkgs, lib, ... }:
let
  core-dir = pkgs.writeTextDir "core.py"
    (builtins.readFile ../scripts/darwin26/core.py);
  memory-script = pkgs.writeText "memory_mcp.py"
    (builtins.readFile ../scripts/darwin26/memory_mcp.py);
  tool-groups = pkgs.writeText "tool_groups.json"
    (builtins.readFile ../config/tool_groups.json);
  tool-tiers = pkgs.writeText "tool_tiers.json"
    (builtins.readFile ../config/tool_tiers.json);
in {
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
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
      MEMORY_FILE      = "/etc/sojus/memory.json";
      REMINDERS_FILE   = "/etc/sojus/reminders.json";
      TOOL_GROUPS_FILE = "/etc/sojus/tool_groups.json";
      TOOL_TIERS_FILE  = "/etc/sojus/tool_tiers.json";
    };

    serviceConfig = {
      Type             = "simple";
      User             = "sojus-core";
      Group            = "sojus-core";
      EnvironmentFile  = "/etc/sojus/config.env";
      ExecStart        = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with fastapi --with httpx --with anthropic uvicorn core:app --app-dir ${core-dir} --host 0.0.0.0 --port 3001";
      Restart          = "on-failure";
      RestartSec       = "10s";
      NoNewPrivileges  = true;
      PrivateTmp       = true;
      ReadWritePaths   = [ "/etc/sojus" ];
    };
  };

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
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
      MEMORY_FILE = "/etc/sojus/memory.json";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "sojus-core";
      Group           = "sojus-core";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with fastmcp fastmcp run ${memory-script} --transport streamable-http --host 0.0.0.0 --port 8010";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ "/etc/sojus" ];
    };
  };

  # Konfig-JSONs aus dem Nix-Store in /etc/sojus/ synchronisieren.
  # Wird bei jedem nixos-rebuild switch aktualisiert.
  system.activationScripts.sojus-tool-groups = {
    deps = [ "users" ];
    text = ''
      install -m 0644 -o sojus-core -g sojus-core ${tool-groups} /etc/sojus/tool_groups.json
      install -m 0644 -o sojus-core -g sojus-core ${tool-tiers} /etc/sojus/tool_tiers.json
    '';
  };

  networking.firewall.allowedTCPPorts = [ 3001 8010 ];
}
