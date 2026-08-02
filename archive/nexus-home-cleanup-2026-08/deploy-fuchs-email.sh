#!/usr/bin/env bash
# deploy-fuchs-email.sh — E-Mail MCP auf darwin26 deployen
# Ausführen mit: sudo bash /home/fuchs/sojus-setup/deploy-fuchs-email.sh
set -e

if [ "$(id -u)" != "0" ]; then
  echo "FEHLER: Bitte als root ausführen: sudo bash $0"
  exit 1
fi

echo "════════════════════════════════════════════"
echo "  FUCHS-EMAIL DEPLOYMENT (darwin26)"
echo "════════════════════════════════════════════"

echo "--- Schritt 1: Server-Script kopieren ---"
mkdir -p /etc/sojus
cp /home/fuchs/sojus-setup/fuchs-email-server.py /etc/sojus/fuchs-email-server.py
chmod 644 /etc/sojus/fuchs-email-server.py
echo "  ✅ fuchs-email-server.py kopiert"

echo "--- Schritt 2: Env-Datei erstellen ---"
if [ -f /etc/sojus/fuchs-email.env ]; then
  echo "  ✅ fuchs-email.env existiert bereits"
else
  cat > /etc/sojus/fuchs-email.env << 'EOF'
# SMTP / IMAP Server
EMAIL_SMTP_HOST=mail.your-server.de
EMAIL_SMTP_PORT=465
EMAIL_IMAP_HOST=mail.your-server.de
EMAIL_IMAP_PORT=993

# Passwörter pro Account (alle drei Accounts, gleiches Passwort oder unterschiedliche)
EMAIL_PASS_HOFPAUSE=PASSWORT_HIER
EMAIL_PASS_ARTEIGEN=PASSWORT_HIER
EMAIL_PASS_WEITES_FELD=PASSWORT_HIER

# Standard-Absender wenn kein from_address angegeben
EMAIL_DEFAULT_FROM=jonas@hofpause.info

# MCP Port
EMAIL_MCP_PORT=8013
EOF
  chmod 600 /etc/sojus/fuchs-email.env
  chown root:root /etc/sojus/fuchs-email.env
  echo "  ✅ fuchs-email.env erstellt"
  echo "  ⚠️  Passwörter noch eintragen: sudo nano /etc/sojus/fuchs-email.env"
fi

echo "--- Schritt 3: NixOS-Modul kopieren ---"
cp /home/fuchs/sojus-setup/fuchs-email.nix /etc/nixos/sys/darwin26/fuchs-email.nix
echo "  ✅ fuchs-email.nix kopiert"

echo "--- Schritt 4: default.nix aktualisieren ---"
if grep -q "fuchs-email.nix" /etc/nixos/sys/darwin26/default.nix; then
  echo "  ✅ fuchs-email.nix bereits eingetragen"
else
  sed -i 's|./fuchs-discord.nix|./fuchs-discord.nix\n    ./fuchs-email.nix|' /etc/nixos/sys/darwin26/default.nix
  echo "  ✅ fuchs-email.nix in default.nix eingetragen"
fi

echo "--- Schritt 5: core.py aktualisieren ---"
if grep -q "fuchs-email" /etc/sojus/core.py; then
  echo "  ✅ fuchs-email bereits in core.py"
else
  sed -i 's|"fuchs-shell":.*"http://192.168.1.40:8012/mcp",|"fuchs-shell":             "http://192.168.1.40:8012/mcp",\n    "fuchs-email":             "http://127.0.0.1:8013/mcp",|' /etc/sojus/core.py
  echo "  ✅ fuchs-email in core.py eingetragen"
fi

cp /etc/sojus/core.py /home/fuchs/sojus-setup/core.py
echo "  ✅ sojus-setup/core.py synchronisiert"

echo "--- Schritt 6: Git staging ---"
git -C /etc/nixos add sys/darwin26/fuchs-email.nix sys/darwin26/default.nix 2>/dev/null || true

echo "--- Schritt 7: NixOS rebuild ---"
nixos-rebuild switch --flake /etc/nixos#darwin26

echo "--- Schritt 8: Sojus-Core neu starten ---"
systemctl restart sojus-core.service

echo "--- Schritt 9: Status ---"
sleep 8
for svc in fuchs-email.service sojus-core.service; do
  STATUS=$(systemctl is-active "$svc" 2>/dev/null)
  [ "$STATUS" = "active" ] && echo "  ✅ $svc" || echo "  ❌ $svc: $STATUS"
done

echo ""
echo "════════════════════════════════════════════"
echo "  FERTIG"
echo "════════════════════════════════════════════"
echo ""
echo "Passwörter eintragen (falls noch nicht gemacht):"
echo "  sudo nano /etc/sojus/fuchs-email.env"
echo "  sudo systemctl restart fuchs-email.service"
