# Neue Instanz "kaira" — eigener User/Service/Home, kein Zugriff auf Jonas'
# Daten. Alle Namen (User "kaira", Service "kaira-agent", Home /var/lib/kaira)
# ergeben sich aus den Defaults von modules/sojus-agent.nix, da instanceName
# hier zum ersten Mal frei gewählt werden kann (kein Bestandsschutz nötig).
#
# ANTHROPIC_API_KEY: sekretsPath zeigt bewusst auf dieselbe Datei wie die
# jonas-Instanz (/etc/sojus/config.env) — Jonas hat für den ersten Rollout
# explizit erlaubt, vorerst denselben Anthropic-Key zu teilen. Sobald ein
# eigener Key existiert: eigenen sops-Secret-Eintrag über modules/sojus-secrets.nix
# anlegen und secretsPath hier auf /etc/sojus/kaira.env umbiegen.
#
# MCP-Tools: bewusst leer. kaira hat noch keinen definierten Aufgabenbereich
# jenseits des NC-Talk-Bots (siehe nc-talk-bot.nix) — Tools kommen dazu, sobald
# klar ist, was kaira tatsächlich braucht (via modules/sojus-mcp.nix).
import ../modules/sojus-agent.nix {
  instanceName = "kaira";
  port         = 3010; # apiPort default = 3011

  secretsPath  = "/etc/sojus/config.env";

  # Explizit statt Default, weil nc-talk-bot.nix denselben Wert als
  # KAIRA_API_KEY braucht, um Hermes' OpenAI-kompatible API anzusprechen —
  # bei Änderung hier auch dort nachziehen.
  hermesApiKey = "hermes-internal-key-kaira-change-in-prod";

  soulMd = ./kaira-SOUL.md;
}
