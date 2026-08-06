# Parametrisiertes Hermes-Agent-Modul: eine Instanz = Engine (OpenAI-kompatible
# API auf `port`) + zugehörige Chat-API/Context-Store (auf `apiPort`) + eigener
# System-User + eigene SOUL.md-Persona.
#
# Curry-Muster wie bei ldap-user-manager.nix: erst Instanz-Parameter, dann die
# eigentliche NixOS-Modulfunktion. Aufruf siehe instances/jonas.nix bzw.
# instances/kaira.nix.
#
# systemPromptBlock / platformToolsetBlock / mcpServersBlock sind komplett
# vorformatierte YAML-Fragmente (inkl. eigener Top-Level-Keys, ab Spalte 0),
# die 1:1 in die generierte hermes-config.yaml eingefügt werden — bewusst kein
# Nix->YAML-Rendering hier, damit die bestehende, live verifizierte
# hermes.nix-Config (siehe deren Kommentare zu tool_search/platform_toolsets-
# Platzierung) für die jonas-Instanz byte-identisch bleibt.
{ instanceName
, port
, soulMd
, apiPort            ? port + 1
, agentUser          ? instanceName
, serviceName        ? "${instanceName}-agent"
, userHome           ? "/var/lib/${agentUser}"
, secretsPath        ? "/etc/sojus/${instanceName}.env"
, apiUser            ? "${instanceName}-api"
, apiServiceName     ? "${instanceName}-api"
, dbDir              ? "/var/lib/${apiUser}"
, attachmentsDir     ? "${dbDir}/attachments"
, model              ? "claude-haiku-4-5-20251001"
, hermesApiKey       ? "hermes-internal-key-${instanceName}-change-in-prod"
, systemPromptBlock  ? ""
, platformToolsetBlock ? ""
, mcpServersBlock    ? ""
}:
{ config, pkgs, lib, ... }:

let
  soulFile = pkgs.writeText "${instanceName}-SOUL.md" (builtins.readFile soulMd);

  hermesConfig = pkgs.writeText "${instanceName}-hermes-config.yaml" ''
    model:
      default: "${model}"
      provider: "anthropic"

    ${systemPromptBlock}
    # "on" statt "auto" erzwingen: "auto" bridged Tool-Schemas nur wenn sie
    # >=10% des Context-Fensters fressen (Fallback: fixer 20k-Token-Cutoff),
    # unser Tool-Payload lag knapp DARUNTER und "auto" ließ die vollen Schemas
    # durch -> ~15k Prompt-Tokens für "hallo" + Anthropic-Timeouts. Bei reinen
    # Config-Inhalt-Änderungen (wie dieser YAML-Datei) restartet ein
    # `nixos-rebuild switch` den Service NICHT automatisch — danach immer
    # manuell `systemctl restart ${serviceName}`.
    tools:
      tool_search:
        enabled: on

    ${platformToolsetBlock}
    ${mcpServersBlock}
    platforms:
      api_server:
        enabled: true
        extra:
          key: "${hermesApiKey}"
  '';

  sojusApiScript = pkgs.writeText "${instanceName}-api-server.py"
    (builtins.readFile ../scripts/darwin26/sojus-api-server.py);

  sojusApiPython = pkgs.python3.withPackages (ps: with ps; [
    fastapi
    uvicorn
    python-multipart
    websockets
    httpx
  ]);
in {
  # ── Agent-Engine ──────────────────────────────────────────────────────────
  users.users.${agentUser} = {
    isSystemUser = true;
    group        = agentUser;
    home         = userHome;
    createHome   = true;
  };
  users.groups.${agentUser} = {};

  systemd.services.${serviceName} = {
    description = "${instanceName}-Agent (Hermes/Nous Research) — OpenAI-kompatibler API-Server, Port ${toString port}";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    # Hermes' Terminal-Tool braucht bash/git/curl/jq/python3 für Shell-Kommandos,
    # die es selbst ausführt (siehe hermes.nix-Vorlage).
    path = [ pkgs.bash pkgs.git pkgs.curl pkgs.jq pkgs.python3 ];

    environment = {
      HOME                 = userHome;
      HERMES_HOME          = "${userHome}/.hermes";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      UV_CACHE_DIR         = "${userHome}/.cache/uv";
      LD_LIBRARY_PATH      = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
      API_SERVER_ENABLED   = "true";
      API_SERVER_PORT      = toString port;
      API_SERVER_HOST      = "0.0.0.0";
      API_SERVER_KEY       = hermesApiKey;
      HERMES_PROVIDER      = "anthropic";
      HERMES_MODEL         = "anthropic/${model}";
    };

    serviceConfig = {
      Type            = "simple";
      User            = agentUser;
      Group           = agentUser;
      EnvironmentFile = secretsPath;
      ExecStartPre    = pkgs.writeShellScript "${serviceName}-setup" ''
        mkdir -p ${userHome}/.hermes
        install -m 600 ${hermesConfig} ${userHome}/.hermes/config.yaml
        [ -e ${userHome}/.hermes/SOUL.md ] || install -m 600 ${soulFile} ${userHome}/.hermes/SOUL.md
      '';
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --from 'hermes-agent[mcp]' --with aiohttp python -m hermes_cli.main gateway run";
      Restart         = "on-failure";
      RestartSec      = "15s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ userHome ];
    };
  };

  # ── Chat-API / Context-Store ──────────────────────────────────────────────
  users.users.${apiUser} = {
    isSystemUser = true;
    group        = apiUser;
    home         = dbDir;
    createHome   = true;
  };
  users.groups.${apiUser} = {};

  systemd.tmpfiles.rules = [
    "d ${dbDir} 0750 ${apiUser} ${apiUser} - -"
    "d ${attachmentsDir} 0750 ${apiUser} ${apiUser} - -"
  ];

  systemd.services.${apiServiceName} = {
    description = "${instanceName} Chat API — Context-Store + REST + WebSocket, Port ${toString apiPort}";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      SOJUS_API_DB_DIR          = dbDir;
      SOJUS_API_ATTACHMENTS_DIR = attachmentsDir;
      SOJUS_API_PORT            = toString apiPort;
      HERMES_URL                = "http://127.0.0.1:${toString port}/v1/chat/completions";
      HERMES_API_KEY            = hermesApiKey;
      HERMES_MODEL              = model;
    };

    serviceConfig = {
      Type            = "simple";
      User            = apiUser;
      Group           = apiUser;
      ExecStart       = "${sojusApiPython}/bin/python3 ${sojusApiScript}";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
      ReadWritePaths  = [ dbDir attachmentsDir ];
    };
  };

  # Nur LAN-Reichweite, wie beim bisherigen Jonas-Setup — kein öffentlicher
  # Port-Forward für Hermes/API-Server auf darwin26.
  networking.firewall.allowedTCPPorts = [ port apiPort ];
}
