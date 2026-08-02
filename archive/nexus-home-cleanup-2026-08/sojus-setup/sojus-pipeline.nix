{ config, pkgs, lib, ... }:
{
  systemd.services.sojus-pipeline = {
    description = "Sojus Pipeline — OpenAI-Bridge zu n8n";
    after = [ "network.target" "n8n.service" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      ExecStart = "${pkgs.python3}/bin/python3 /etc/sojus/sojus-pipeline.py";
      Restart = "always";
      RestartSec = "10s";
      DynamicUser = true;
      Environment = [
        "PIPELINE_PORT=3001"
        "N8N_WEBHOOK_URL=http://localhost:5678/webhook/sojus-firmenchef"
      ];
      EnvironmentFile = "/etc/sojus/sojus-pipeline.env";
    };
  };
}
