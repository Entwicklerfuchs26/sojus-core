{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "sojus-pipeline.py"
    (builtins.readFile ../scripts/darwin26/sojus-pipeline.py);
in {
  systemd.services.sojus-pipeline = {
    description = "Sojus Pipeline — OpenAI-Bridge zu n8n";
    after = [ "network.target" "n8n.service" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      ExecStart    = "${pkgs.python3}/bin/python3 ${script}";
      Restart      = "always";
      RestartSec   = "10s";
      DynamicUser  = true;
      Environment  = [
        "PIPELINE_PORT=3001"
        "N8N_WEBHOOK_URL=http://localhost:5678/webhook/sojus-firmenchef"
      ];
      EnvironmentFile = "/etc/sojus/sojus-pipeline.env";
    };
  };
}
