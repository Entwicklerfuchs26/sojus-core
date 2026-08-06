# NC Talk Bot — Webhook-Empfänger für Nextcloud Talk auf edaphos.weites-feld.org
# (siehe scripts/darwin26/nc-talk-bot-server.py), leitet erlaubte Nachrichten an
# die kaira-Agent-Instanz weiter (instances/kaira.nix, Port 3010) und postet
# die Antwort als Bot zurück.
#
# WICHTIG: edaphos.weites-feld.org läuft NICHT auf darwin26 (eigener,
# separater Nextcloud-VPS) — die Bot-Registrierung selbst
# ("occ talk:bot:install") muss auf JENEM Host laufen, nicht hier. Dieses
# Modul stellt nur den darwin26-seitigen Webhook-Empfänger bereit.
#
# Netzwerk: kein öffentlicher Port-Forward — der VPS erreicht darwin26 über
# eine FritzBox-WireGuard-Verbindung (VPS als Peer, geroutet ins Heimnetz).
# darwin26 braucht dafür KEIN eigenes wg-Interface: die FritzBox routet den
# VPS-Traffic direkt zur bestehenden LAN-IP 192.168.1.26. Der Webhook-Port
# wird deshalb nicht pauschal freigegeben, sondern nur für die Quell-IP des
# VPS im Tunnel (vpsWireguardTunnelIp) — die ergibt sich erst nach dem
# FritzBox-Setup (siehe Deploy-Notiz), deshalb vorerst Platzhalter.
{ config, pkgs, lib, ... }:

let
  script = pkgs.writeText "nc-talk-bot-server.py"
    (builtins.readFile ../scripts/darwin26/nc-talk-bot-server.py);

  port = 3012;

  # TODO(Jonas): durch die tatsächliche Tunnel-IP des VPS ersetzen, sobald
  # die FritzBox-WireGuard-Verbindung steht (siehe Deploy-Notiz/occ-Anleitung).
  # Bis dahin lauscht der Service zwar auf 0.0.0.0:3012, ist aber ohne diese
  # Firewall-Freigabe von nirgendwo außerhalb von darwin26 selbst erreichbar.
  vpsWireguardTunnelIp = "REPLACE_ME";

  python = pkgs.python3.withPackages (ps: with ps; [ fastapi uvicorn httpx ]);

  secretsModule = import ../modules/sojus-secrets.nix {
    instanceName  = "kaira";
    secretsPrefix = "kaira";
    entries = [
      { slug = "nc-talk-bot"; owner = "kaira-nc-talk-bot"; }
    ];
  };
in {
  imports = [ secretsModule ];

  users.users.kaira-nc-talk-bot = {
    isSystemUser = true;
    group        = "kaira-nc-talk-bot";
    home         = "/var/lib/kaira-nc-talk-bot";
    createHome   = true;
  };
  users.groups.kaira-nc-talk-bot = {};

  systemd.services.nc-talk-bot = {
    description = "NC Talk Bot (kaira) — Webhook-Empfänger für edaphos.weites-feld.org, Port ${toString port}";
    after       = [ "network-online.target" "kaira-agent.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME               = "/var/lib/kaira-nc-talk-bot";
      NEXTCLOUD_HOST     = "https://edaphos.weites-feld.org";
      # Wiederverwendet dieselbe entwicklerfuchs-Session wie mcp-nextcloud.nix
      # (nur lesend: Gruppenmitglieder + Conversation-Typ abfragen).
      NEXTCLOUD_USERNAME = "entwicklerfuchs";
      NC_TALK_BOT_NAME          = "kaira";
      NC_TALK_BOT_ALLOWED_GROUP = "wfd_aibot";
      KAIRA_URL      = "http://127.0.0.1:3010/v1/chat/completions";
      # Muss mit hermesApiKey in instances/kaira.nix übereinstimmen.
      KAIRA_API_KEY  = "hermes-internal-key-kaira-change-in-prod";
      NC_TALK_BOT_PORT = toString port;
    };

    serviceConfig = {
      Type            = "simple";
      User            = "kaira-nc-talk-bot";
      Group           = "kaira-nc-talk-bot";
      # Zwei EnvironmentFiles: eigenes Bot-Secret + NEXTCLOUD_PASSWORD aus dem
      # bestehenden mcp-nextcloud-Secret (systemd liest EnvironmentFile als
      # root vor dem Rechte-Drop, Dateimodus der Quelldatei ist dafür egal).
      EnvironmentFile = [
        "/etc/sojus/kaira-nc-talk-bot.env"
        "/etc/sojus/mcp-nextcloud.env"
      ];
      ExecStart       = "${python}/bin/python3 ${script}";
      Restart         = "on-failure";
      RestartSec      = "10s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  # Bewusst KEIN networking.firewall.allowedTCPPorts (das würde 3012 fürs
  # ganze LAN öffnen) — nur die WireGuard-Tunnel-IP des VPS darf rein.
  # extraCommands/extraStopCommands statt nftables-Syntax, da darwin26 (Stand
  # dieser Config) keine nftables.enable-Option gesetzt hat, also noch auf
  # dem klassischen iptables-Backend läuft.
  networking.firewall.extraCommands = ''
    iptables -A nixos-fw -p tcp --dport ${toString port} -s ${vpsWireguardTunnelIp} -j nixos-fw-accept
  '';
  networking.firewall.extraStopCommands = ''
    iptables -D nixos-fw -p tcp --dport ${toString port} -s ${vpsWireguardTunnelIp} -j nixos-fw-accept || true
  '';
}
