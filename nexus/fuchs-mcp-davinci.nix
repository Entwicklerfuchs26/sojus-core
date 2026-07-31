{ config, pkgs, lib, ... }:

let
  # Phase 2: interner Port 19006, mcp-approval-proxy uebernimmt extern 9006.
  port = 19006;

  # DaVinci Resolve Scripting-Pfad wird dynamisch zur Laufzeit per find ermittelt,
  # da der Nix-Store-Hash sich bei Updates ändert. Store enthaelt pro Version
  # mehrere Pfade (Haupt-Derivation, -bwrap, -fhsenv-profile, -fhsenv-rootfs,
  # -init) mit zufaelligem Hash-Praefix - "sort | tail -1" sortiert nach Hash
  # statt nach Inhalt und trifft dadurch oft einen Pfad ohne Scripting-Modul.
  # Deshalb hier jeden Kandidaten direkt auf die Datei pruefen statt den
  # Verzeichnisnamen zu erraten.
  startScript = pkgs.writeShellScript "start-fuchs-mcp-davinci" ''
    RESOLVE=$(
      for d in $(find /nix/store -maxdepth 1 -type d -name "*-davinci-resolve-[0-9]*" 2>/dev/null); do
        [ -f "$d/Developer/Scripting/Modules/DaVinciResolveScript.py" ] || continue
        ver=$(basename "$d" | sed -E 's/.*-davinci-resolve-([0-9.]+).*/\1/')
        echo "$ver $d"
      done | sort -V | tail -1 | cut -d' ' -f2-
    )

    if [ -z "$RESOLVE" ]; then
      echo "DaVinci Resolve Scripting-Module nicht gefunden in Nix-Store" >&2
      echo "Service pausiert bis DaVinci Resolve installiert ist." >&2
      exit 1
    fi

    export PYTHONPATH="$RESOLVE/Developer/Scripting/Modules''${PYTHONPATH:+:$PYTHONPATH}"
    export RESOLVE_SCRIPT_LIB="$RESOLVE/libs/Fusion/fusionscript.so"

    # Versionspin: mcp-proxy 0.12.0 + mcp>=2.0.0 bricht mit
    # "ImportError: cannot import name 'request_ctx' from mcp.server.lowlevel.server"
    # (PyPI-Versionsdrift, ohne Pin holt uvx sonst das neueste mcp).
    exec ${pkgs.uv}/bin/uvx --with "mcp<2.0.0" mcp-proxy==0.12.0 \
      --port ${toString port} --host 127.0.0.1 \
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
