{ config, pkgs, lib, ... }:

let
  cfg = config.services.sojusApi;

  sojusApiScript = pkgs.writeText "sojus-api-server.py"
    (builtins.readFile ../scripts/darwin26/sojus-api-server.py);

  python = pkgs.python3.withPackages (ps: with ps; [
    fastapi
    uvicorn
    python-multipart
    websockets
    httpx
  ]);
in {
  options.services.sojusApi = {
    dbDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/sojus-api";
      description = "Verzeichnis für context.db (SQLite Context-Store des Sojus-Chats).";
    };

    attachmentsDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/sojus-api/attachments";
      description = "Verzeichnis für hochgeladene Chat-Anhänge.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 7430;
      description = "Port der Sojus-Chat-REST-API/WebSocket.";
    };

    hermesUrl = lib.mkOption {
      type = lib.types.str;
      # Hermes läuft als eigener Service auf demselben Host, siehe darwin26/hermes.nix.
      default = "http://127.0.0.1:3002/v1/chat/completions";
      description = "OpenAI-kompatibler Chat-Completions-Endpunkt von Hermes.";
    };

    # Muss mit hermesApiKey in darwin26/hermes.nix übereinstimmen.
    hermesApiKey = lib.mkOption {
      type = lib.types.str;
      default = "hermes-internal-key-change-in-prod";
      description = "API-Key für den Hermes-API-Server (siehe darwin26/hermes.nix).";
    };

    hermesModel = lib.mkOption {
      type = lib.types.str;
      default = "claude-haiku-4-5-20251001";
      description = "Modell-ID, die Hermes für Chat-Completions verwenden soll.";
    };
  };

  config = {
    users.users.sojus-api = {
      isSystemUser = true;
      group        = "sojus-api";
      home         = cfg.dbDir;
      createHome   = true;
    };
    users.groups.sojus-api = {};

    systemd.tmpfiles.rules = [
      "d ${cfg.dbDir} 0750 sojus-api sojus-api - -"
      "d ${cfg.attachmentsDir} 0750 sojus-api sojus-api - -"
    ];

    systemd.services.sojus-api = {
      description = "Sojus Chat API — Context-Store + REST + WebSocket, Port ${toString cfg.port}";
      after       = [ "network-online.target" ];
      wants       = [ "network-online.target" ];
      wantedBy    = [ "multi-user.target" ];

      environment = {
        SOJUS_API_DB_DIR          = cfg.dbDir;
        SOJUS_API_ATTACHMENTS_DIR = cfg.attachmentsDir;
        SOJUS_API_PORT            = toString cfg.port;
        HERMES_URL                = cfg.hermesUrl;
        HERMES_API_KEY            = cfg.hermesApiKey;
        HERMES_MODEL              = cfg.hermesModel;
      };

      serviceConfig = {
        Type            = "simple";
        User            = "sojus-api";
        Group           = "sojus-api";
        ExecStart       = "${python}/bin/python3 ${sojusApiScript}";
        Restart         = "on-failure";
        RestartSec      = "10s";
        NoNewPrivileges = true;
        PrivateTmp      = true;
        ReadWritePaths  = [ cfg.dbDir cfg.attachmentsDir ];
      };
    };

    # Nur LAN-Reichweite: darwin26 hat keinen öffentlichen Port-Forward für
    # 7430 (wie die MCP-Server auch), die Firewall-Freigabe hier betrifft nur
    # das lokale Netz.
    networking.firewall.allowedTCPPorts = [ cfg.port ];
  };
}
