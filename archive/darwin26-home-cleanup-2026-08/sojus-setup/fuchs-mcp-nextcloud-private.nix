{ config, pkgs, lib, ... }: {

  # sojus-mcp user/group ist bereits in mcp-nextcloud.nix definiert

  systemd.services.fuchs-mcp-nextcloud-private = {
    description = "Fuchs - Private Nextcloud MCP Server (cbcoutinho)";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    environment = {
      NEXTCLOUD_HOST = "https://cloud.sternenhof.space";
      NEXTCLOUD_USERNAME = "fuchs";
      MCP_DEPLOYMENT_MODE = "single_user_basic";
      HOME = "/var/lib/sojus-mcp";
      UV_PYTHON = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
        pkgs.openssl.out
        pkgs.glib
      ];
    };

    serviceConfig = {
      Type = "simple";
      User = "sojus-mcp";
      Group = "sojus-mcp";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-nextcloud-private.env";
      ExecStart = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 nextcloud-mcp-server run --host 0.0.0.0 --port 8009 --transport streamable-http";
      Restart = "on-failure";
      RestartSec = "30s";
      NoNewPrivileges = true;
      PrivateTmp = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8009 ];
}
