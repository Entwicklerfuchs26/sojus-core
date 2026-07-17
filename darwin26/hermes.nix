{ config, pkgs, lib, ... }:

let
  hermesPort   = 3002;
  # Testschlüssel — für Produktion: in agenix-Secret auslagern
  hermesApiKey = "hermes-internal-key-change-in-prod";

  hermesConfig = pkgs.writeText "hermes-config.yaml" ''
    model:
      default: "anthropic/claude-sonnet-4-6"
      provider: "anthropic"

    # Terminal-Tool explizit ausgeschlossen — kein Shell-Zugriff über API
    platform_toolsets:
      api_server:
        - hermes-base
        - web
        - files
        - vision
        - mcp

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
      '';
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --from hermes-agent hermes gateway start";
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
