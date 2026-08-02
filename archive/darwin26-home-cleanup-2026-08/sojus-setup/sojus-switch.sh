#!/usr/bin/env bash
# sojus-switch — Sojus Backend schnell umschalten
# Verwendung: sudo sojus-switch [auto|claude|ollama] [modell]
#
# Beispiele:
#   sudo sojus-switch claude              → immer Claude (aktuelles Modell)
#   sudo sojus-switch claude haiku        → immer Claude Haiku
#   sudo sojus-switch claude sonnet       → immer Claude Sonnet
#   sudo sojus-switch claude opus         → immer Claude Opus
#   sudo sojus-switch ollama              → immer Ollama (aktuelles Modell)
#   sudo sojus-switch ollama qwen3:8b     → Ollama mit spezifischem Modell
#   sudo sojus-switch auto                → automatisches Routing (Standard)
#   sudo sojus-switch status              → aktuellen Status anzeigen

ENV_FILE=/etc/sojus/config.env

if [ "$(id -u)" != "0" ]; then
  echo "Bitte als root ausführen: sudo sojus-switch $*"
  exit 1
fi

CMD="${1:-status}"
MODEL_ARG="${2:-}"

# Modell-Shortcuts für Claude
case "$MODEL_ARG" in
  haiku)  CLAUDE_MODEL="claude-haiku-4-5-20251001" ;;
  sonnet) CLAUDE_MODEL="claude-sonnet-4-6" ;;
  opus)   CLAUDE_MODEL="claude-opus-4-7" ;;
  "")     CLAUDE_MODEL="" ;;
  *)      CLAUDE_MODEL="$MODEL_ARG" ;;
esac

case "$CMD" in
  status)
    echo "=== Sojus Backend-Status ==="
    FORCE=$(grep "^FORCE_BACKEND=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "")
    CLAUDE=$(grep "^ANTHROPIC_MODEL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "claude-sonnet-4-6")
    OLLAMA=$(grep "^OLLAMA_MODEL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "qwen3.5:9b")
    HAS_KEY=$(grep "^ANTHROPIC_API_KEY=" "$ENV_FILE" 2>/dev/null | grep -v "=$" | wc -l)

    echo "  API-Key:       $([ "$HAS_KEY" -gt 0 ] && echo '✅ gesetzt' || echo '❌ fehlt')"
    echo "  FORCE_BACKEND: ${FORCE:-auto (nicht gesetzt)}"
    echo "  Claude-Modell: $CLAUDE"
    echo "  Ollama-Modell: $OLLAMA"
    ;;

  auto)
    sed -i '/^FORCE_BACKEND=/d' "$ENV_FILE"
    echo "✅ Automatisches Routing aktiv (einfach→Ollama, komplex→Claude)"
    systemctl restart sojus-core.service
    echo "✅ sojus-core neu gestartet"
    ;;

  claude)
    sed -i '/^FORCE_BACKEND=/d' "$ENV_FILE"
    echo "FORCE_BACKEND=anthropic" >> "$ENV_FILE"
    if [ -n "$CLAUDE_MODEL" ]; then
      sed -i '/^ANTHROPIC_MODEL=/d' "$ENV_FILE"
      echo "ANTHROPIC_MODEL=$CLAUDE_MODEL" >> "$ENV_FILE"
      echo "✅ Claude aktiviert: $CLAUDE_MODEL"
    else
      CURRENT=$(grep "^ANTHROPIC_MODEL=" "$ENV_FILE" | cut -d= -f2 || echo "claude-sonnet-4-6")
      echo "✅ Claude aktiviert: $CURRENT"
    fi
    systemctl restart sojus-core.service
    echo "✅ sojus-core neu gestartet"
    ;;

  ollama)
    sed -i '/^FORCE_BACKEND=/d' "$ENV_FILE"
    echo "FORCE_BACKEND=ollama" >> "$ENV_FILE"
    if [ -n "$MODEL_ARG" ]; then
      sed -i '/^OLLAMA_MODEL=/d' "$ENV_FILE"
      echo "OLLAMA_MODEL=$MODEL_ARG" >> "$ENV_FILE"
      echo "✅ Ollama aktiviert: $MODEL_ARG"
    else
      CURRENT=$(grep "^OLLAMA_MODEL=" "$ENV_FILE" | cut -d= -f2 || echo "qwen3.5:9b")
      echo "✅ Ollama aktiviert: $CURRENT"
    fi
    systemctl restart sojus-core.service
    echo "✅ sojus-core neu gestartet"
    ;;

  *)
    echo "Verwendung: sudo sojus-switch [status|auto|claude|ollama] [modell]"
    echo ""
    echo "  status               → aktuellen Stand anzeigen"
    echo "  auto                 → automatisches Routing"
    echo "  claude [haiku|sonnet|opus]  → immer Claude"
    echo "  ollama [modellname]  → immer Ollama"
    exit 1
    ;;
esac
