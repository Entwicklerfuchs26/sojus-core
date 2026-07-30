{ config, pkgs, lib, ... }:
{
  imports = [
    ./secrets.nix
    ./tools.nix
    ./hermes.nix
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
