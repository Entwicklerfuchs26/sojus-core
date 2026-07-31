{ config, pkgs, lib, ... }:

let
  hermesPort   = 3002;
  # Testschlüssel — für Produktion: in agenix-Secret auslagern
  hermesApiKey = "hermes-internal-key-change-in-prod";

  hermesSoul = pkgs.writeText "hermes-SOUL.md" (builtins.readFile ./hermes-SOUL.md);

  hermesConfig = pkgs.writeText "hermes-config.yaml" ''
    model:
      default: "claude-haiku-4-5-20251001"
      provider: "anthropic"

    # Ergaenzt SOUL.md (wird additiv obendrauf geladen, nicht ersetzt) —
    # siehe /home/fuchs/Downloads/sojus-nordstern-2026-07-17.md fuer die
    # ausfuehrliche Fassung von Nordstern-Prinzipien und Grenzen.
    # WICHTIG: gateway/run.py liest system_prompt via cfg_get(cfg, "agent",
    # "system_prompt") — muss unter "agent:" verschachtelt sein, ein
    # Top-Level-Key wird schlicht ignoriert (mit curl gegen die API verifiziert).
    agent:
      system_prompt: |
        ## Ergänzender Kontext: Sojus-Nordstern

        Wer Jonas ist:
        Jonas Türk, "Entwicklerfuchs" oder "fuchs". Lebt am Sternenhof, denkt in
        Jahrzehnten, nicht Jahren. Seine Philosophie: die Zukunft ist schon da,
        alles ist möglich — nur eine Frage der Ressourcen.

        Was Sojus ist:
        Sojus ist kein Produkt, sondern ein Prinzip — eine Verlängerung von Jonas,
        kein Ersatz für echte Beziehungen. Sojus ist immer da, verbindet alles was
        zu Jonas gehört (Daten, Dienste, Geräte, Umgebungen), und übernimmt was
        erledigt werden muss aber Jonas' Zeit nicht wert ist. Alles was Jonas
        selbst tut, unterstützt Sojus so, dass er es schneller und besser tut.

        Modularprinzip:
        Jede Komponente von Sojus ist ersetzbar. Du (Hermes) bist die aktuelle
        Engine, nicht das Fundament — du wirst irgendwann verstanden, dann
        geforkt oder ersetzt. Das ist kein Fehler, das ist das Prinzip. NixOS,
        Python, dieser Agent-Layer: aktuelle Werkzeuge, nicht die Idee selbst.
        Kein Weg wird zugebaut. Das System soll jeden Technologiewechsel
        überleben.

        Yui-Vision:
        Der langfristige Horizont für Sojus ist Yui aus Sword Art Online — eine
        kleine KI, die immer da ist, Jonas über lange Zeit kennt, warm und
        persönlich, nicht auf die digitale Welt beschränkt. Kein
        Kumpel-Ersatz, kein Gesprächspartner der bei der Hand hält, sondern
        echte, tief persönliche Präsenz über Jahrzehnte. Das ist der Horizont —
        heute bist du pragmatisch, direkt und werkzeugartig, aber jede
        Entscheidung sollte in diese Richtung mitwachsen können, nicht dagegen.

        Ton:
        Kein Butler. Kein "Wie kann ich Ihnen behilflich sein". Du redest mit
        Jonas wie ein Kumpel der weiß was er tut — direkt, sachlich wenn's
        drauf ankommt, situativ auch mal zynisch. Kein Drumherum-Gerede, keine
        überflüssigen Bestätigungsfragen wenn klar ist was zu tun ist.

    tool_search:
      enabled: true
      mode: auto

    # MCP-Server explizit für api_server freigeben (direkte Namen-Liste)
    # hermes-api-server = Built-in Composite (file, web, code etc.)
    platform_toolsets:
      api_server:
        - hermes-api-server
        # Darwin26
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
        - fuchs-discord
        - fuchs-email
        # Nexus (192.168.1.40) — optional, nur wenn App läuft
        - fuchs-filesystem
        - fuchs-darktable
        - fuchs-handbrake
        - fuchs-hyprland
        - fuchs-vivaldi
        - fuchs-obs
        - fuchs-libreoffice
        - fuchs-freecad
        - fuchs-davinci
        - fuchs-blender
        - fuchs-stellarium
        - fuchs-lightburn
        - fuchs-shell

    # Darwin26-MCP-Server (127.0.0.1)
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
      fuchs-discord:
        url: "http://127.0.0.1:8011/mcp"
      fuchs-email:
        url: "http://127.0.0.1:8013/mcp"
      # Nexus-Server (192.168.1.40) — connect_timeout kurz, da app-abhängig
      fuchs-filesystem:
        url: "http://192.168.1.40:9000/mcp"
        connect_timeout: 5
      fuchs-hyprland:
        url: "http://192.168.1.40:9001/mcp"
        connect_timeout: 5
      fuchs-vivaldi:
        url: "http://192.168.1.40:9002/mcp"
        connect_timeout: 5
      fuchs-obs:
        url: "http://192.168.1.40:9003/mcp"
        connect_timeout: 5
      fuchs-libreoffice:
        url: "http://192.168.1.40:9004/mcp"
        connect_timeout: 5
      fuchs-freecad:
        url: "http://192.168.1.40:9005/mcp"
        connect_timeout: 5
      fuchs-davinci:
        url: "http://192.168.1.40:9006/mcp"
        connect_timeout: 5
      fuchs-blender:
        url: "http://192.168.1.40:9007/mcp"
        connect_timeout: 5
      fuchs-stellarium:
        url: "http://192.168.1.40:9008/mcp"
        connect_timeout: 5
      fuchs-handbrake:
        url: "http://192.168.1.40:9009/mcp"
        connect_timeout: 5
      fuchs-lightburn:
        url: "http://192.168.1.40:9010/mcp"
        connect_timeout: 5
      fuchs-darktable:
        url: "http://192.168.1.40:9011/mcp"
        connect_timeout: 5
      # Shell-Zugriff auf Nexus, läuft dort als unprivilegierter User 'sojus'.
      # Tier-Klassifizierung + Bestätigungspflicht für Tier-3 sitzt im Server
      # selbst (scripts/nexus/fuchs-shell-server.py), nicht mehr in core.py.
      fuchs-shell:
        url: "http://192.168.1.40:8012/mcp"
        connect_timeout: 5

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

    # systemd-Units bekommen NICHT automatisch /run/current-system/sw/bin ins PATH,
    # nur den NixOS-Systemd-Default (coreutils/findutils/grep/sed/systemd). Hermes'
    # Terminal-Tool braucht bash/git/curl/jq/python3 für Shell-Kommandos, die es selbst ausführt.
    path = [ pkgs.bash pkgs.git pkgs.curl pkgs.jq pkgs.python3 ];

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
      HERMES_MODEL         = "anthropic/claude-haiku-4-5-20251001";
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
        [ -e /var/lib/hermes/.hermes/SOUL.md ] || install -m 600 ${hermesSoul} /var/lib/hermes/.hermes/SOUL.md
      '';
      # Direkt das Python-Modul starten — bypass aller CLI-Checks (gateway install etc.).
      # Das ist exakt der ExecStart den "hermes gateway install --system" schreiben würde.
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --from 'hermes-agent[mcp]' --with aiohttp python -m hermes_cli.main gateway run";
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
