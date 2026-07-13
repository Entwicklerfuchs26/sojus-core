{ config, pkgs, lib, ... }:
let
  script = pkgs.writeText "fuchs-email-server.py"
    (builtins.readFile ../scripts/darwin26/fuchs-email-server.py);
in {
  users.users.fuchs-email = {
    isSystemUser = true;
    group        = "fuchs-email";
    home         = "/var/lib/fuchs-email";
    createHome   = true;
  };
  users.groups.fuchs-email = {};

  systemd.services.fuchs-email = {
    description = "Fuchs – E-Mail MCP Server";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    wantedBy    = [ "multi-user.target" ];

    environment = {
      HOME                 = "/var/lib/fuchs-email";
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      UV_CACHE_DIR         = "/var/lib/fuchs-email/.cache/uv";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib pkgs.zlib pkgs.openssl.out pkgs.glib
      ];
    };

    serviceConfig = {
      Type            = "simple";
      User            = "fuchs-email";
      Group           = "fuchs-email";
      EnvironmentFile = "/etc/sojus/fuchs-email.env";
      ExecStart       = "${pkgs.uv}/bin/uv run --python ${pkgs.python3}/bin/python3 --with fastmcp ${script}";
      Restart         = "on-failure";
      RestartSec      = "30s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };
}
