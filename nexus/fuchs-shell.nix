{ config, pkgs, lib, ... }:

let
  # fuchs-shell-server.py importiert mcp_risk_classifier als Sibling-Modul —
  # beide müssen im selben Verzeichnis landen, deshalb runCommand statt
  # writeText (das nur eine einzelne Datei erzeugt).
  srcDir = pkgs.runCommand "fuchs-shell-src" {} ''
    mkdir -p $out
    cp ${pkgs.writeText "fuchs-shell-server.py" (builtins.readFile ../scripts/nexus/fuchs-shell-server.py)} $out/fuchs-shell-server.py
    cp ${pkgs.writeText "mcp_risk_classifier.py" (builtins.readFile ../scripts/shared/mcp_risk_classifier.py)} $out/mcp_risk_classifier.py
  '';
  toolTiers = pkgs.writeText "tool_tiers.json" (builtins.readFile ../config/tool_tiers.json);

  port = 8012;

  # Muss mit approvalApiToken in darwin26/mcp-approval-service.nix identisch sein.
  approvalApiToken = "mcp-approval-internal-token-change-in-prod";
in {
  # Läuft als 'sojus' (definiert in modules/ai/sojus.nix), NICHT als 'fuchs' —
  # eigenes, unprivilegiertes Home statt Zugriff auf Jonas' echtes Home
  # (SSH-Keys, Repo mit Push-Rechten etc.). sojus hat bereits eine eng
  # gewhitelistete NOPASSWD-Sudoers-Regel für genau diesen Service, siehe
  # /etc/nixos/nixos-config/modules/ai/sojus.nix.
  systemd.services.fuchs-shell = {
    description = "Fuchs Shell — MCP Shell-Zugriff auf Nexus (Port ${toString port}, User sojus)";
    wantedBy    = [ "multi-user.target" ];
    after       = [ "network.target" ];

    environment = {
      HOME                 = "/home/sojus";
      UV_CACHE_DIR         = "/home/sojus/.cache/uv";
      # Zwingt uv auf Nix-Python statt eigenes generisches Python herunterzuladen —
      # auf darwin26 ohne das ein harter Crash ("stub-ld", siehe mcp-approval-service.nix).
      # nexus hat nix-ld, wäre also vermutlich glimpflicher ausgegangen, aber
      # gleiches Muster vorsorglich übernommen statt sich drauf zu verlassen.
      UV_PYTHON            = "${pkgs.python3}/bin/python3";
      UV_PYTHON_PREFERENCE = "only-system";
      TOOL_TIERS_FILE      = "/etc/sojus/tool_tiers.json";
      # mcp-approval-service läuft auf darwin26 (Port siehe dortiges Modul).
      APPROVAL_URL          = "http://192.168.1.26:8014";
      APPROVAL_API_TOKEN    = approvalApiToken;
      APPROVAL_WAIT_TIMEOUT = "90";
    };

    serviceConfig = {
      Type       = "simple";
      User       = "sojus";
      Group      = "sojus";
      ExecStart  = "${pkgs.uv}/bin/uvx fastmcp run ${srcDir}/fuchs-shell-server.py --transport streamable-http --host 192.168.1.40 --port ${toString port}";
      Restart    = "on-failure";
      RestartSec = "10s";
    };
  };

  # tool_tiers.json aus dem Nix-Store nach /etc/sojus/ synchronisieren, wie
  # vormals sojus-tool-groups in archive/sojus-core-legacy/sojus-core.nix.
  # Wird bei jedem nixos-rebuild switch aktualisiert. Weltlesbar (0644) reicht,
  # der Service läuft ohnehin unprivilegiert als sojus.
  system.activationScripts.fuchs-shell-tool-tiers = {
    deps = [ "users" ];
    text = ''
      mkdir -p /etc/sojus
      install -m 0644 ${toolTiers} /etc/sojus/tool_tiers.json
    '';
  };
}
