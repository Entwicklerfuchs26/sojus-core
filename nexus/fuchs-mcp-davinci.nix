{ config, pkgs, lib, ... }:

let
  port = 9006;

  # DaVinci Resolve Scripting-Pfad wird dynamisch zur Laufzeit per find ermittelt,
  # da der Nix-Store-Hash sich bei Updates ändert.
  startScript = pkgs.writeShellScript "start-fuchs-mcp-davinci" ''
    RESOLVE=$(find /nix/store -maxdepth 1 -name "*-davinci-resolve-[0-9]*" \
      ! -name "*-bwrap" 2>/dev/null | sort | tail -1)

    if [ -z "$RESOLVE" ] || \
       [ ! -f "$RESOLVE/Developer/Scripting/Modules/DaVinciResolveScript.py" ]; then
      echo "DaVinci Resolve Scripting-Module nicht gefunden in Nix-Store" >&2
      echo "Service pausiert bis DaVinci Resolve installiert ist." >&2
      exit 1
    fi

    export PYTHONPATH="$RESOLVE/Developer/Scripting/Modules''${PYTHONPATH:+:$PYTHONPATH}"
    export RESOLVE_SCRIPT_LIB="$RESOLVE/libs/Fusion/fusionscript.so"

    exec ${pkgs.uv}/bin/uvx mcp-proxy \
      --port ${toString port} --host 192.168.1.40 \
      --transport streamablehttp \
      --pass-environment \
      --named-server davinci "${pkgs.uv}/bin/uvx resolve-mcp"
  '';
in {
  systemd.services.fuchs-mcp-davinci = {
    description = "Fuchs – DaVinci Resolve MCP via mcp-proxy (HTTP, Port ${toString port})";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME = "/home/fuchs";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "fuchs";
      ExecStart  = "${startScript}";
      Restart    = "on-failure";
      RestartSec = "30s";
    };
  };
}
