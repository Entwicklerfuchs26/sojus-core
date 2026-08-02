{ config, pkgs, lib, ... }:
let
  hostname = "sojus.sternenhof.space";
in {
  services.open-webui = {
    enable = true;
    port = 8080;
    host = "127.0.0.1";
    environmentFile = "/etc/sojus/open-webui.env";
    environment = {
      WEBUI_NAME = "Sojus";
      ENABLE_SIGNUP = "False";
      DEFAULT_USER_ROLE = "admin";
      ENABLE_COMMUNITY_SHARING = "False";
      DO_NOT_TRACK = "True";
      SCARF_NO_ANALYTICS = "True";
      # Pipeline als "Modell"-Backend — kein direkter Ollama/OpenAI-Zugriff
      # OPENAI_API_BASE_URL und OPENAI_API_KEY kommen aus environmentFile
      OLLAMA_BASE_URL = "";
      ENABLE_OLLAMA_API = "False";
    };
  };

  services.nginx.virtualHosts.${hostname} = {
    forceSSL = true;
    sslCertificate    = "/var/lib/nginx/ssl/wildcard-chain.crt";
    sslCertificateKey = "/var/lib/nginx/ssl/wildcard.sternenhof.space.key";
    locations."/" = {
      proxyPass = "http://127.0.0.1:8080";
      proxyWebsockets = true;
      extraConfig = ''
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 100M;
      '';
    };
  };
}
