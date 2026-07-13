{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "mcp-supplement-server.py"
    (builtins.readFile ../scripts/darwin26/mcp-supplement-server.py);
in {
  users.users.sojus-mcp-supplement = {
    isSystemUser = true;
    group        = "sojus-mcp-supplement";
    home         = "/var/lib/sojus-mcp-supplement";
    createHome   = true;
  };
  users.groups.sojus-mcp-supplement = {};

  systemd.services.sojus-mcp-supplement = {
    description = "Sojus – Nextcloud Supplement MCP Server";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      NEXTCLOUD_HOST       = "https://edaphos.weites-feld.org";
      NEXTCLOUD_USERNAME   = "entwicklerfuchs";
      HOME                 = "/var/lib/sojus-mcp-supplement";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "sojus-mcp-supplement";
      Group           = "sojus-mcp-supplement";
      EnvironmentFile = "/etc/sojus/mcp-nextcloud.env";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with httpx fastmcp run ${script} --transport streamable-http --host 0.0.0.0 --port 8001";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8001 ];
}
