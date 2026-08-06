# Parametrisierte MCP-Server-Liste für eine Sojus-Agent-Instanz.
#
# Die bestehenden 15 darwin26-MCP-Server (fuchs-mcp-*.nix, mcp-nextcloud.nix
# usw.) bleiben bewusst UNVERÄNDERT als eigenständige, bereits laufende
# Produktiv-Services — sie hier hineinzuziehen wäre ein riskanter Umbau von
# Diensten, die Jonas täglich nutzt, ohne Mehrwert für dieses Modul. Dieses
# Modul ist für NEUE, pro-Instanz-eigene MCP-Server gedacht (z.B. spätere
# kaira-spezifische Tools), die absichtlich NICHT die Zugangsdaten/Endpunkte
# der bestehenden Jonas-Server teilen.
#
# `servers` ist eine Liste von:
#   { name = "beispiel"; script = ../scripts/darwin26/beispiel-server.py;
#     secretsPath = null; extraEnv = {}; }
# Jeder Eintrag bekommt einen eigenen System-User "${instanceName}-mcp-${name}"
# und einen eigenen internen Port ab `basePort` (fortlaufend), erreichbar nur
# auf 127.0.0.1 — Firewall-Freigabe/Approval-Proxy-Anbindung ist bewusst nicht
# Teil dieses Moduls (siehe mcp-approval-proxy.nix als Vorbild, sobald eine
# Instanz tatsächlich MCP-Tools bekommt, die durch den Approval-Flow sollen).
{ instanceName
, basePort
, servers ? []
}:
{ config, pkgs, lib, ... }:

let
  mkServer = index: s:
    let
      user = "${instanceName}-mcp-${s.name}";
      port = basePort + index;
      scriptFile = pkgs.writeText "${user}-server.py" (builtins.readFile s.script);
    in {
      users.users.${user} = {
        isSystemUser = true;
        group        = user;
        home         = "/var/lib/${user}";
        createHome   = true;
      };
      users.groups.${user} = {};

      systemd.services.${user} = {
        description = "${instanceName} — ${s.name} MCP Server (Port ${toString port})";
        after       = [ "network-online.target" ];
        wants       = [ "network-online.target" ];
        wantedBy    = [ "multi-user.target" ];

        environment = {
          HOME                 = "/var/lib/${user}";
          UV_PYTHON            = "${pkgs.python3}/bin/python3";
          UV_PYTHON_PREFERENCE = "only-system";
          LD_LIBRARY_PATH = lib.makeLibraryPath [
            pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
          ];
        } // (s.extraEnv or {});

        serviceConfig = {
          Type            = "simple";
          User            = user;
          Group           = user;
          ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${scriptFile} --transport streamable-http --host 127.0.0.1 --port ${toString port}";
          Restart         = "on-failure";
          RestartSec      = "30s";
          NoNewPrivileges = true;
          PrivateTmp      = true;
        } // lib.optionalAttrs (s.secretsPath or null != null) {
          EnvironmentFile = s.secretsPath;
        };
      };
    };

  serverModules = lib.imap0 mkServer servers;
in
  lib.mkMerge serverModules
