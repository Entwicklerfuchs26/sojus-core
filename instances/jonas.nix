# Jonas' bestehende Sojus-Instanz — extrahiert aus dem früheren
# darwin26/hermes.nix + darwin26/sojus-api.nix, unverändert funktional:
# gleicher User "hermes", gleicher Service-Name "hermes-agent", gleicher Port
# 3002, gleiches API-Server-Setup auf 7430 mit identischem Key, gleiche
# mcp_servers/platform_toolsets-Config. Alle Overrides unten bestehen NUR,
# damit sich an den bereits laufenden Produktiv-Services (User, Home-Dir,
# Secrets-Pfad, API-Key) nichts ändert — instanceName "sojus" ist die
# Produkt-/Persona-Identität, nicht der technische Ressourcenname.
let
  systemPromptBlock = ''
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
  '';

  # Bewusst NUR darwin26-lokale + Nexus-Server, siehe ursprüngliche
  # Begründung in der Git-Historie von hermes.nix (Nexus-Kreativ-Tools
  # scheiterten bei jedem Start ohne laufende Apps, kosteten Prompt-Tokens +
  # Timeout-Risiko im Sojus-Chat).
  platformToolsetBlock = ''
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
        - fuchs-discord
        - fuchs-email
        - fuchs-sandbox-control
  '';

  mcpServersBlock = ''
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
      fuchs-sandbox-control:
        url: "http://127.0.0.1:8015/mcp"
      # Nexus-Server (192.168.1.40) — connect_timeout kurz, da app-abhängig.
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
      # selbst (scripts/nexus/fuchs-shell-server.py).
      fuchs-shell:
        url: "http://192.168.1.40:8012/mcp"
        connect_timeout: 5
      fuchs-sandbox-control-nexus:
        url: "http://192.168.1.40:9012/mcp"
        connect_timeout: 5
  '';
in
import ../modules/sojus-agent.nix {
  instanceName = "sojus";
  port         = 3002;

  # Exakte Bestandsnamen — NICHT von instanceName ableiten lassen, sonst
  # verliert der laufende Produktiv-Service seinen User/Home/Secrets-Pfad.
  agentUser    = "hermes";
  serviceName  = "hermes-agent";
  userHome     = "/var/lib/hermes";
  secretsPath  = "/etc/sojus/config.env";

  apiPort      = 7430;
  hermesApiKey = "hermes-internal-key-change-in-prod";

  soulMd = ../darwin26/hermes-SOUL.md;

  inherit systemPromptBlock platformToolsetBlock mcpServersBlock;
}
