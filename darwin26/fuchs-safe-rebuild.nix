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
    # "nixos-container update" ist die klassische imperative Lösung dafür,
    # sucht aber per NIX_PATH nach einer Legacy configuration.nix und
    # scheitert deshalb bei unserem Flake-Setup ("file 'nixos-config' was
    # not found", live reproduziert). Stattdessen: stop + Rootfs löschen +
    # start — Testcontainer sind ohnehin Wegwerf-State, alle echten Daten
    # liegen in den bindMounts (nixos-copy, sojus-core), nicht im Rootfs
    # selbst. Start provisioniert dann komplett frisch aus der aktuellen
    # Config. Non-fatal, falls ein Container gerade nicht existiert/läuft.
    for c in sandbox-sojus sandbox-darwin; do
      log "Reprovisioniere Container-Rootfs: $c"
      sudo /run/current-system/sw/bin/systemctl stop "container@$c.service" 2>/dev/null || true
      sudo /run/current-system/sw/bin/rm -rf "/var/lib/nixos-containers/$c"
      sudo /run/current-system/sw/bin/systemctl start "container@$c.service" \
        || log "WARNUNG: Neustart von $c fehlgeschlagen (ignoriert)"
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

        # Manueller Container-Reprovision ohne vollen Rebuild-Zyklus (gleicher
        # Schritt läuft auch automatisch am Ende von safe-rebuild-darwin26.sh).
        # Exakte Pfade, kein Wildcard — nur diese beiden Wegwerf-Rootfs.
        { command = "/run/current-system/sw/bin/rm -rf /var/lib/nixos-containers/sandbox-sojus";  options = [ "NOPASSWD" ]; }
        { command = "/run/current-system/sw/bin/rm -rf /var/lib/nixos-containers/sandbox-darwin"; options = [ "NOPASSWD" ]; }

        # Rebuild: nur über den geprüften Wrapper (build-vm vor switch, Git-Audit-Trail)
        { command = "/home/fuchs/bin/safe-rebuild-darwin26.sh"; options = [ "NOPASSWD" ]; }
        { command = "/home/fuchs/bin/safe-rebuild-darwin26.sh *"; options = [ "NOPASSWD" ]; }

        # Rohe nixos-rebuild-Aufrufe bleiben absichtlich passwortgeschützt —
        # safe-rebuild-darwin26.sh ist der einzige NOPASSWD-Rebuild-Pfad.
      ];
    }
  ];
}
