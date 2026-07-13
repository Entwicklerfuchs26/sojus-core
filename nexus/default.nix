# Sojus Nexus-Module: alle 12 MCP-Services (stdio→HTTP) + Firewall-Ports
{ config, pkgs, lib, ... }:

{
  imports = [
    ./fuchs-mcp-filesystem.nix   # Port 9000 – Dateisystem (mcp-proxy → npx)
    ./fuchs-mcp-hyprland.nix     # Port 9001 – Hyprland WM
    ./fuchs-mcp-vivaldi.nix      # Port 9002 – Vivaldi Browser CDP
    ./fuchs-mcp-obs.nix          # Port 9003 – OBS Studio (mcp-proxy → npx)
    ./fuchs-mcp-libreoffice.nix  # Port 9004 – LibreOffice Writer
    ./fuchs-mcp-freecad.nix      # Port 9005 – FreeCAD (mcp-proxy → uvx)
    ./fuchs-mcp-davinci.nix      # Port 9006 – DaVinci Resolve (mcp-proxy → uvx)
    ./fuchs-mcp-blender.nix      # Port 9007 – Blender 3D (mcp-proxy → uvx)
    ./fuchs-mcp-stellarium.nix   # Port 9008 – Stellarium Planetarium
    ./fuchs-mcp-handbrake.nix    # Port 9009 – HandBrake Video-Encode
    ./fuchs-mcp-lightburn.nix    # Port 9010 – LightBurn Laser-CAD
    ./fuchs-mcp-darktable.nix    # Port 9011 – Darktable Fotografie
  ];

  # Ports sind localhost-only (127.0.0.1) — kein Firewall-Öffnen nötig.
  # Für WireGuard-Zugriff von darwin26: entweder SSH-Tunnel über wg0,
  # oder Binding auf wg0-IP ergänzen (dann hier freischalten).
}
