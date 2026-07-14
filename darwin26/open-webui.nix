{ config, pkgs, lib, ... }:
let
  hostname = "sojus.sternenhof.space";
in {
  services.open-webui = {
    enable = true;
    port   = 8080;
    host   = "127.0.0.1";
    environmentFile = "/etc/sojus/open-webui.env";
    environment = {
      WEBUI_NAME              = "Sojus";
      ENABLE_SIGNUP           = "False";
      DEFAULT_USER_ROLE       = "admin";
      ENABLE_COMMUNITY_SHARING = "False";
      DO_NOT_TRACK            = "True";
      SCARF_NO_ANALYTICS      = "True";
      OLLAMA_BASE_URL         = "";
      ENABLE_OLLAMA_API       = "False";
      # Explizit setzen — DynamicUser setzt HOME normalerweise automatisch, aber
      # manche Python-Libs rufen expanduser("~") auf bevor systemd es propagiert hat.
      HOME                    = "/var/lib/open-webui";
      # Korrekte öffentliche URL damit Cookies, Redirects und WebSockets stimmen
      WEBUI_URL               = "https://${hostname}";
      # CORS auf die eigene Domain beschränken
      CORS_ALLOW_ORIGIN       = "https://${hostname}";

      # Audio: STT + TTS für alle User freischalten (sind schon Default, aber explizit).
      # Engine-Wahl erfolgt im Admin-UI → "Web API" = rein browser-seitige Web Speech
      # API / SpeechSynthesis, kein Server-Roundtrip, kein Modell-Download.
      # Server-seitiges Whisper (faster_whisper) ist im Nix-Package nicht gebündelt.
      USER_PERMISSIONS_CHAT_STT = "True";
      USER_PERMISSIONS_CHAT_TTS = "True";
      # Sprach-Hint für eventuelle spätere Server-Whisper-Aktivierung
      WHISPER_LANGUAGE          = "de";
    };
  };

  services.nginx.virtualHosts.${hostname} = {
    forceSSL          = true;
    sslCertificate    = "/var/lib/nginx/ssl/wildcard-chain.crt";
    sslCertificateKey = "/var/lib/nginx/ssl/wildcard.sternenhof.space.key";
    locations."/" = {
      proxyPass       = "http://127.0.0.1:8080";
      proxyWebsockets = true;
      extraConfig = ''
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 100M;
      '';
    };
  };
}
