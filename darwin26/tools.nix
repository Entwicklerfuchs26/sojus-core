{ config, pkgs, lib, ... }:
{
  environment.systemPackages = with pkgs; [
    sops
    age
    ssh-to-age
  ];
}
