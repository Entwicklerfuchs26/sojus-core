# Parametrisierte sops-Secret-Definitionen für eine Sojus-Agent-Instanz.
# Analog zu darwin26/secrets.nix, aber pro Instanz mit eigenem Prefix statt
# hart codierten "sojus/*"-Namen — jede Instanz bekommt so ihre eigenen
# sops-Einträge, ohne dass sich Instanzen gegenseitig Secrets lesen können.
#
# `entries` ist eine Liste von:
#   { slug = "nc-talk-bot"; owner = "kaira-nc-talk-bot"; group = owner; mode = "0400"; }
# Erzeugt sops.secrets."${secretsPrefix}/${slug}" mit Pfad
# /etc/sojus/${secretsPrefix}-${slug}.env.
#
# Secret-INHALTE selbst werden hier NICHT verwaltet — die gehören verschlüsselt
# in /etc/nixos/secrets.yaml (sudo sops /etc/nixos/secrets.yaml), dieses Modul
# deklariert nur, welche Keys erwartet werden und wohin sie entschlüsselt
# werden.
{ instanceName
, secretsPrefix ? instanceName
, entries ? []
}:
{ config, pkgs, lib, ... }:

{
  sops.secrets = lib.listToAttrs (map (e: {
    name = "${secretsPrefix}/${e.slug}";
    value = {
      path  = "/etc/sojus/${secretsPrefix}-${e.slug}.env";
      owner = e.owner or "root";
      group = e.group or (e.owner or "root");
      mode  = e.mode or "0400";
    };
  }) entries);
}
