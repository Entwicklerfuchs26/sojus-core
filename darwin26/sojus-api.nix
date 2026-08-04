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
