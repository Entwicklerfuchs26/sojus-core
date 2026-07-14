{ config, pkgs, lib, ... }:
{
  users.users.sojus-mcp = {
    isSystemUser = true;
    group        = "sojus-mcp";
    home         = "/var/lib/sojus-mcp";
    createHome   = true;
  };
  users.groups.sojus-mcp = {};

  systemd.services.sojus-mcp-nextcloud = {
    description = "Sojus - Nextcloud MCP Server";
    after  = [ "network-online.target" ];
    wants  = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    environment = {
      NEXTCLOUD_HOST      = "https://edaphos.weites-feld.org";
      NEXTCLOUD_USERNAME  = "entwicklerfuchs";
      MCP_DEPLOYMENT_MODE = "single_user_basic";
      HOME                 = "/var/lib/sojus-mcp";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      SSL_CERT_FILE        = "/etc/ssl/certs/ca-bundle.crt";
      REQUESTS_CA_BUNDLE   = "/etc/ssl/certs/ca-bundle.crt";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "sojus-mcp";
      Group           = "sojus-mcp";
      EnvironmentFile = "/etc/sojus/mcp-nextcloud.env";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 nextcloud-mcp-server run --host 0.0.0.0 --transport streamable-http";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8000 ];
}
