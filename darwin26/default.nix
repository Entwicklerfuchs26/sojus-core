{ config, pkgs, lib, ... }:
{
  imports = [
    ./secrets.nix
    ./tools.nix
    # Hermes-Engine + Chat-API, jetzt modularisiert (modules/sojus-agent.nix)
    # statt fest verdrahtet — siehe instances/ für die konkreten Instanzen.
    # jonas.nix ersetzt das frühere hermes.nix + sojus-api.nix 1:1 funktional
    # (siehe archive/hermes-sojus-api-legacy-2026-08/ für die Vorgänger).
    ../instances/jonas.nix
    ../instances/kaira.nix
    (import ../modules/sojus-sandbox.nix { instanceName = "kaira"; })
    # ./nc-talk-bot.nix  # TEMP auskommentiert: Secret kaira/nc-talk-bot fehlt noch in secrets.yaml
    ./containers.nix
    ./sandbox-sojus-control.nix
    ./fuchs-safe-rebuild.nix
    ./mcp-approval-service.nix
    ./mcp-approval-proxy.nix
    ./open-webui.nix
    ./fuchs-discord.nix
    ./fuchs-email.nix
    ./mcp-nextcloud.nix
    ./mcp-supplement.nix
    ./mcp-openproject.nix
    ./fuchs-mcp-vikunja.nix
    ./fuchs-mcp-homeassistant.nix
    ./fuchs-mcp-n8n.nix
    ./fuchs-mcp-jellyfin.nix
    ./fuchs-mcp-immich.nix
    ./fuchs-mcp-anilist.nix
    ./fuchs-mcp-nextcloud-private.nix
  ];
}
