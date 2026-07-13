# Integration ins nexus NixOS-Flake

## 1. Flake-Input hinzufügen (/etc/nixos/flake.nix)

```nix
inputs = {
  # ... bestehende inputs ...

  sojus-core = {
    url = "path:/home/fuchs/sojus-core";
    inputs.nixpkgs.follows = "nixpkgs";
  };
};

outputs = { self, nixpkgs, sojus-core, ... }: {
  nixosConfigurations.nexus = nixpkgs.lib.nixosSystem {
    # ...
    modules = [
      # ... bestehende module ...
      sojus-core.nixosModules.nexus   # ← NEU
    ];
  };
};
```

## 2. OBS Secret anlegen (einmalig, manuell)

```bash
sudo mkdir -p /etc/sojus/nexus
echo "OBS_WEBSOCKET_PASSWORD=6Smso7Sj2lplcFd7" | sudo tee /etc/sojus/nexus/fuchs-mcp-obs.env
sudo chmod 640 /etc/sojus/nexus/fuchs-mcp-obs.env
sudo chown root:users /etc/sojus/nexus/fuchs-mcp-obs.env
```

## 3. NixOS rebuild auf nexus

```bash
sudo nixos-rebuild switch --flake /etc/nixos#nexus
```

## 4. .claude.json umstellen (NACH erfolgreichem Start aller Services)

Für jeden stdio-Server den Eintrag ersetzen durch:

```json
"fuchs-filesystem":  { "type": "http", "url": "http://127.0.0.1:9000/mcp" },
"fuchs-hyprland":    { "type": "http", "url": "http://127.0.0.1:9001/mcp" },
"fuchs-vivaldi":     { "type": "http", "url": "http://127.0.0.1:9002/mcp" },
"fuchs-obs":         { "type": "http", "url": "http://127.0.0.1:9003/mcp" },
"fuchs-libreoffice": { "type": "http", "url": "http://127.0.0.1:9004/mcp" },
"fuchs-freecad":     { "type": "http", "url": "http://127.0.0.1:9005/mcp" },
"fuchs-davinci":     { "type": "http", "url": "http://127.0.0.1:9006/mcp" },
"fuchs-blender":     { "type": "http", "url": "http://127.0.0.1:9007/mcp" },
"fuchs-stellarium":  { "type": "http", "url": "http://127.0.0.1:9008/mcp" },
"fuchs-handbrake":   { "type": "http", "url": "http://127.0.0.1:9009/mcp" },
"fuchs-lightburn":   { "type": "http", "url": "http://127.0.0.1:9010/mcp" },
"fuchs-darktable":   { "type": "http", "url": "http://127.0.0.1:9011/mcp" }
```

Sojus Core auf darwin26 greift stattdessen auf 192.168.1.40:9000-9011 zu.
