{ config, pkgs, lib, ... }:

let
  hermesPort   = 3002;
  # Testschlüssel — für Produktion: in agenix-Secret auslagern
  hermesApiKey = "hermes-internal-key-change-in-prod";

  hermesConfig = pkgs.writeText "hermes-config.yaml" ''
    model:
      default: "claude-sonnet-4-6"
      provider: "anthropic"

    # MCP-Server explizit für api_server freigeben (direkte Namen-Liste)
    # hermes-api-server = Built-in Composite (file, web, code etc.)
    platform_toolsets:
      api_server:
        - hermes-api-server
        - nc-weites-feld
        - nc-weites-feld-extra
        - fuchs-openproject
        - fuchs-vikunja
        - fuchs-homeassistant
        - fuchs-n8n
        - fuchs-jellyfin
        - fuchs-immich
        - fuchs-anilist
        - nc-sternenhof
        - fuchs-sojus-memory
        - fuchs-discord
        - fuchs-email

    # Alle Darwin26-MCP-Server als HTTP-Endpoints
    mcp_servers:
      nc-weites-feld:
        url: "http://127.0.0.1:8000/mcp"
      nc-weites-feld-extra:
        url: "http://127.0.0.1:8001/mcp"
      fuchs-openproject:
        url: "http://127.0.0.1:8002/mcp"
      fuchs-vikunja:
        url: "http://127.0.0.1:8003/mcp"
      fuchs-homeassistant:
        url: "http://127.0.0.1:8004/mcp"
      fuchs-n8n:
        url: "http://127.0.0.1:8005/mcp"
      fuchs-jellyfin:
        url: "http://127.0.0.1:8006/mcp"
      fuchs-immich:
        url: "http://127.0.0.1:8007/mcp"
      fuchs-anilist:
        url: "http://127.0.0.1:8008/mcp"
      nc-sternenhof:
        url: "http://127.0.0.1:8009/mcp"
      fuchs-sojus-memory:
        url: "http://127.0.0.1:8010/mcp"
      fuchs-discord:
        url: "http://127.0.0.1:8011/mcp"
      fuchs-email:
        url: "http://127.0.0.1:8013/mcp"

    platforms:
      api_server:
        enabled: true
        extra:
          key: "${hermesApiKey}"
  '';
in {
  users.users.hermes = {
    isSystemUser = true;
    group        = "hermes";
    home         = "/var/lib/hermes";
    createHome   = true;
  };
  users.groups.hermes = {};

  systemd.services.hermes-agent = {
    description = "Hermes Agent (Nous Research) — OpenAI-kompatibler API-Server, Port ${toString hermesPort}";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/hermes";
      # HERMES_HOME zeigt auf das .hermes-Verzeichnis selbst (nicht dessen Parent).
      # _load_gateway_config() liest $HERMES_HOME/config.yaml für MCP-Server.
      HERMES_HOME          = "/var/lib/hermes/.hermes";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      UV_CACHE_DIR         = "/var/lib/hermes/.cache/uv";
      LD_LIBRARY_PATH      = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
      # API-Server
      API_SERVER_ENABLED   = "true";
      API_SERVER_PORT      = toString hermesPort;
      API_SERVER_HOST      = "0.0.0.0";
      API_SERVER_KEY       = hermesApiKey;
      # Provider
      HERMES_PROVIDER      = "anthropic";
      HERMES_MODEL         = "anthropic/claude-sonnet-4-6";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "hermes";
      Group           = "hermes";
      # ANTHROPIC_API_KEY kommt aus bestehendem agenix-Secret
      EnvironmentFile = "/etc/sojus/config.env";
      ExecStartPre    = pkgs.writeShellScript "hermes-setup" ''
        mkdir -p /var/lib/hermes/.hermes
        install -m 600 ${hermesConfig} /var/lib/hermes/.hermes/config.yaml
        echo "=== Hermes Config installiert aus: ${hermesConfig} ===" >&2
        cat /var/lib/hermes/.hermes/config.yaml >&2
        echo "=== Config-Ende ===" >&2
      '';
      # Direkt das Python-Modul starten — bypass aller CLI-Checks (gateway install etc.).
      # Das ist exakt der ExecStart den "hermes gateway install --system" schreiben würde.
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --from 'hermes-agent[mcp]' python -m hermes_cli.main gateway run";
      Restart         = "on-failure";
      RestartSec      = "15s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ "/var/lib/hermes" ];
    };
  };

  # Nur intern erreichbar — kein öffentlicher Port
  networking.firewall.allowedTCPPorts = [ hermesPort ];
}
