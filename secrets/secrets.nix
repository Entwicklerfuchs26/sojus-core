let
  nexus = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILrdaUQ5hjOM9tXrf/8VMZa9lV6P78DYZVIIEoUJGG8X root@nexus";
  allKeys = [ nexus ];
in {
  "fuchs-mcp-obs-env.age".publicKeys = allKeys;
}
