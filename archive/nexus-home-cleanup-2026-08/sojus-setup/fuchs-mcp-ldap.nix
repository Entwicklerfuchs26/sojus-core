{ config, pkgs, lib, ... }: {

  users.users.fuchs-mcp-ldap = {
    isSystemUser = true;
    group        = "fuchs-mcp-ldap";
    home         = "/var/lib/fuchs-mcp-ldap";
    createHome   = true;
  };
  users.groups.fuchs-mcp-ldap = {};

  systemd.services.fuchs-mcp-ldap = {
    description = "Fuchs – LDAP MCP Server";
    after       = [ "network-online.target" "openldap.service" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-mcp-ldap";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
        pkgs.openssl.out
        pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-mcp-ldap";
      Group           = "fuchs-mcp-ldap";
      EnvironmentFile = "/etc/sojus/fuchs-mcp-ldap.env";
      ExecStart       = "${pkgs.uv}/bin/uvx --python ${pkgs.python3}/bin/python3 --with ldap3 fastmcp run /etc/sojus/fuchs-mcp-ldap-server.py --transport streamable-http --host 0.0.0.0 --port 8008";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

  networking.firewall.allowedTCPPorts = [ 8008 ];
}
