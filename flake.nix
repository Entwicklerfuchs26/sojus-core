{
  description = "Sojus Core – KI-Agent MCP Services für nexus und darwin26";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: {
    nixosModules = {
      # Alle 12 nexus stdio→HTTP MCP-Services + fuchs-shell + sojus-User
      nexus   = import ./nexus/default.nix;
      # Darwin26 Sojus-Core + 15 MCP-Services (Schritt 3 Phase 2: darwin26 migration)
      darwin26 = import ./darwin26/default.nix;
    };
  };
}
