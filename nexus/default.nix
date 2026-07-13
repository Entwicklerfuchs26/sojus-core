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

  # Ports für Sojus Core auf darwin26 (192.168.1.26) öffnen
  networking.firewall.allowedTCPPorts = [ 9000 9001 9002 9003 9004 9005 9006 9007 9008 9009 9010 9011 ];
}
