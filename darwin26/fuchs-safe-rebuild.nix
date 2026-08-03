{ config, pkgs, lib, ... }:

let
  # Gleiches Muster wie nixos-config/modules/ai/sojus.nix auf Nexus: erst
  # build-vm als Test, erst bei Erfolg switch, davor/danach git-Commit als
  # Audit-Trail. Für darwin26 (Prod-Host mit Nextcloud/HA/Jellyfin/Immich/...)
  # bewusst NICHT direkt switch ohne Testbuild.
  safeRebuildScript = pkgs.writeShellScript "safe-rebuild-darwin26" ''
    #!/usr/bin/env bash
    set -euo pipefail

    DESCRIPTION="''${1:-auto}"
    FLAKE_DIR="/etc/nixos"
    FLAKE_TARGET="darwin26"

    log() { echo "[safe-rebuild] $*"; }
    die() { echo "[safe-rebuild] FEHLER: $*" >&2; exit 1; }

    git_fuchs() {
      git -C "$FLAKE_DIR" \
        -c safe.directory="$FLAKE_DIR" \
        -c user.name="Sojus-Agent" \
        -c user.email="sojus@darwin26" \
        "$@"
    }

    log "Starte sicheren Rebuild: '$DESCRIPTION'"
    git config --global --add safe.directory "$FLAKE_DIR" 2>/dev/null || true

    log "Staging Änderungen..."
    git_fuchs add -A
    if git_fuchs diff --cached --quiet; then
      log "Keine Änderungen im Staging – kein pre-rebuild commit nötig."
    else
      git_fuchs commit -m "pre-rebuild: $DESCRIPTION"
      log "Pre-rebuild commit erstellt."
    fi

    # sojus-core ist ein path:-Flake-Input und wird in flake.lock per NarHash
    # gepinnt. --update-input separat auf build-vm UND switch zu geben, hat
    # live zu einem veralteten Lock geführt (zwei getrennte Resolve-Events,
    # switch landete auf einem älteren NarHash als der tatsächliche
    # Verzeichnisinhalt). Deshalb: Lock EINMAL explizit vorab aktualisieren,
    # danach build-vm/switch ohne eigenes --update-input – beide nutzen dann
    # denselben, bereits geschriebenen Lock-Stand.
    log "Aktualisiere sojus-core Flake-Lock..."
    nix flake lock --update-input sojus-core "$FLAKE_DIR" \
      || die "flake lock update fehlgeschlagen."

    log "Baue VM-Test-Image..."
    sudo nixos-rebuild build-vm --flake "$FLAKE_DIR#$FLAKE_TARGET" \
      || die "build-vm fehlgeschlagen – switch abgebrochen."
    log "VM-Build erfolgreich."

    log "Führe nixos-rebuild switch durch..."
    sudo nixos-rebuild switch --flake "$FLAKE_DIR#$FLAKE_TARGET" \
      || die "switch fehlgeschlagen – System im alten Zustand."
    log "Switch erfolgreich."

    # Deklarative Container werden vom Host-switch NICHT automatisch
    # reprovisioniert, wenn sie zum Zeitpunkt des Switch nicht liefen — das
    # persistente Container-Rootfs bleibt sonst stumm auf dem allerersten
    # Stand hängen (live reproduziert: sojus-uid blieb nach mehreren Switches
    # + Neustarts bei 1000, obwohl die Host-Config schon 29000 evaluierte).
    # nixos-container update ist der explizite, immer funktionierende Weg,
    # unabhängig vom Running-Status. Non-fatal, falls ein Container gerade
    # nicht existiert.
    for c in sandbox-sojus sandbox-darwin; do
      log "Aktualisiere Container-Rootfs: $c"
      sudo nixos-container update "$c" || log "WARNUNG: nixos-container update $c fehlgeschlagen (ignoriert)"
    done

    git_fuchs add -A
    if git_fuchs diff --cached --quiet; then
      git_fuchs commit --allow-empty -m "post-rebuild: $DESCRIPTION – erfolgreich"
    else
      git_fuchs commit -m "post-rebuild: $DESCRIPTION – erfolgreich"
    fi
    log "Fertig. System läuft auf neuem Build."
  '';
in {
  # ── safe-rebuild.sh deployen ─────────────────────────────────────────────
  system.activationScripts.fuchsSafeRebuildBin = {
    deps = [ "users" ];
    text = ''
      install -d -m 750 -o fuchs -g users /home/fuchs/bin
      install -m 750 -o fuchs -g users \
        ${safeRebuildScript} \
        /home/fuchs/bin/safe-rebuild-darwin26.sh
    '';
  };

  # ── Sudoers-Whitelist für fuchs ──────────────────────────────────────────
  # Nur diese Befehle NOPASSWD. Alles andere weiterhin Passwort-Pflicht
  # (kein blanket sudo NOPASSWD für fuchs auf einem Host mit gemeinsam
  # genutzten Diensten).
  security.sudo.extraRules = [
    {
      users = [ "fuchs" ];
      commands = [
        # Testen/Steuern des Sandbox-Containers
        { command = "/run/current-system/sw/bin/systemctl start container@sandbox-sojus.service";  options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl stop container@sandbox-sojus.service";   options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container@sandbox-sojus.service"; options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container@sandbox-sojus.service --no-pager"; options = [ "NOPASSWD" ]; }

        { command = "/run/current-system/sw/bin/systemctl start container@sandbox-darwin.service";  options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl stop container@sandbox-darwin.service";   options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container@sandbox-darwin.service"; options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/systemctl status container@sandbox-darwin.service --no-pager"; options = [ "NOPASSWD" ]; }

        # Manueller Container-Refresh ohne vollen Rebuild-Zyklus (gleicher
        # Schritt läuft auch automatisch am Ende von safe-rebuild-darwin26.sh)
        { command = "/run/current-system/sw/bin/nixos-container update sandbox-sojus";  options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/nixos-container update sandbox-darwin"; options = [ "NOPASSWD" ]; }

        # Rebuild: nur über den geprüften Wrapper (build-vm vor switch, Git-Audit-Trail)
        { command = "/home/fuchs/bin/safe-rebuild-darwin26.sh"; options = [ "NOPASSWD" ]; }
        { command = "/home/fuchs/bin/safe-rebuild-darwin26.sh *"; options = [ "NOPASSWD" ]; }

        # Rohe nixos-rebuild-Aufrufe bleiben absichtlich passwortgeschützt —
        # safe-rebuild-darwin26.sh ist der einzige NOPASSWD-Rebuild-Pfad.
      ];
    }
  ];
}
