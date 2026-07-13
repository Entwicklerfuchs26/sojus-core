{ config, pkgs, lib, ... }:
# Sops-nix managed secrets for all darwin26 sojus services.
# Each secret is the full content of the corresponding .env file.
# Paths match exactly what each service's EnvironmentFile= expects,
# so no changes to individual service modules are required.
#
# To add or update a secret, edit /etc/nixos/secrets.yaml on darwin26:
#   sudo sops /etc/nixos/secrets.yaml
# Then run: sudo nixos-rebuild switch --flake /etc/nixos#darwin26
{
  sops.secrets = {
    # sojus-core: ANTHROPIC_API_KEY, PIPELINE_API_KEY, HA_TOKEN
    "sojus/config" = {
      path  = "/etc/sojus/config.env";
      owner = "sojus-core";
      group = "sojus-core";
      mode  = "0400";
    };

    # Nextcloud MCP (edaphos): NEXTCLOUD_PASSWORD
    # also used by mcp-supplement
    "sojus/mcp-nextcloud" = {
      path  = "/etc/sojus/mcp-nextcloud.env";
      owner = "sojus-mcp";
      group = "sojus-mcp";
      mode  = "0440";
    };

    # Nextcloud private (cloud.sternenhof.space): NEXTCLOUD_PASSWORD
    "sojus/fuchs-mcp-nextcloud-private" = {
      path  = "/etc/sojus/fuchs-mcp-nextcloud-private.env";
      owner = "sojus-mcp";
      group = "sojus-mcp";
      mode  = "0400";
    };

    # Home Assistant MCP: HA_URL, HA_TOKEN
    "sojus/fuchs-mcp-homeassistant" = {
      path  = "/etc/sojus/fuchs-mcp-homeassistant.env";
      owner = "fuchs-mcp-homeassistant";
      group = "fuchs-mcp-homeassistant";
      mode  = "0400";
    };

    # Immich MCP: IMMICH_URL, IMMICH_API_KEY
    "sojus/fuchs-mcp-immich" = {
      path  = "/etc/sojus/fuchs-mcp-immich.env";
      owner = "fuchs-mcp-immich";
      group = "fuchs-mcp-immich";
      mode  = "0400";
    };

    # Jellyfin MCP: JELLYFIN_URL, JELLYFIN_API_KEY
    "sojus/fuchs-mcp-jellyfin" = {
      path  = "/etc/sojus/fuchs-mcp-jellyfin.env";
      owner = "fuchs-mcp-jellyfin";
      group = "fuchs-mcp-jellyfin";
      mode  = "0400";
    };

    # n8n MCP: N8N_URL, N8N_API_KEY
    "sojus/fuchs-mcp-n8n" = {
      path  = "/etc/sojus/fuchs-mcp-n8n.env";
      owner = "fuchs-mcp-n8n";
      group = "fuchs-mcp-n8n";
      mode  = "0400";
    };

    # OpenProject MCP: OPENPROJECT_URL, OPENPROJECT_API_KEY
    "sojus/fuchs-mcp-openproject" = {
      path  = "/etc/sojus/fuchs-mcp-openproject.env";
      owner = "fuchs-mcp-openproject";
      group = "fuchs-mcp-openproject";
      mode  = "0400";
    };

    # Vikunja MCP: VIKUNJA_URL, VIKUNJA_TOKEN
    "sojus/fuchs-mcp-vikunja" = {
      path  = "/etc/sojus/fuchs-mcp-vikunja.env";
      owner = "fuchs-mcp-vikunja";
      group = "fuchs-mcp-vikunja";
      mode  = "0400";
    };

    # AniList MCP: ANILIST_ACCESS_TOKEN
    "sojus/fuchs-mcp-anilist" = {
      path  = "/etc/sojus/fuchs-mcp-anilist.env";
      owner = "fuchs-mcp-anilist";
      group = "fuchs-mcp-anilist";
      mode  = "0400";
    };

    # Discord bot: DISCORD_BOT_TOKEN, DISCORD_ALLOWED_USERS
    "sojus/fuchs-discord" = {
      path  = "/etc/sojus/fuchs-discord.env";
      owner = "fuchs-discord";
      group = "fuchs-discord";
      mode  = "0400";
    };

    # Email: EMAIL_PASS_HOFPAUSE, EMAIL_PASS_ARTEIGEN
    "sojus/fuchs-email" = {
      path  = "/etc/sojus/fuchs-email.env";
      owner = "fuchs-email";
      group = "fuchs-email";
      mode  = "0400";
    };

    # Open WebUI: WEBUI_SECRET_KEY (and other OpenWebUI env vars)
    "sojus/open-webui" = {
      path  = "/etc/sojus/open-webui.env";
      owner = "open-webui";
      group = "open-webui";
      mode  = "0400";
    };
  };
}
