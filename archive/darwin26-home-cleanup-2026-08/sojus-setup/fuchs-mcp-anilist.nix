{ config, pkgs, lib, ... }: {

  users.users.fuchs-mcp-anilist = {
    isSystemUser = true;
    group        = "fuchs-mcp-anilist";
    home         = "/var/lib/fuchs-mcp-anilist";
    createHome   = true;
  };
  users.groups.fuchs-mcp-anilist = {};

  systemd.services.fuchs-mcp-anilist = {
    description = "Fuchs – AniList MCP Server";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME      = "/var/lib/fuchs-mcp-anilist";
      TRANSPORT = "http";
      PORT      = "8008";
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-anilist";
      Group           = "fuchs-mcp-anilist";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-anilist.env";
      ExecStart       = pkgs.writeShellScript "fuchs-mcp-anilist-start" ''
        export PATH="${pkgs.nodejs}/bin:${pkgs.bash}/bin:${pkgs.coreutils}/bin:$PATH"
        exec ${pkgs.nodejs}/bin/npx -y anilist-mcp
      '';
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8008 ];
}
