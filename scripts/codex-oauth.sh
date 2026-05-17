#!/bin/bash
set -eu
case "${1:-}" in
  detect-or-prompt)
    if [ -f "$CODEX_HOME/auth.json" ]; then
      MODE=$(jq -r '.mode // "unknown"' "$CODEX_HOME/auth.json" 2>/dev/null || echo "unknown")
      echo "✓ Codex auth: $MODE (token found at $CODEX_HOME/auth.json)"
      exit 0
    fi
    if [ -n "${OPENAI_API_KEY:-}" ]; then
      echo "✓ Codex auth: API key (env, Codex CLI 0.122+ will auto-write auth.json)"
      exit 0
    fi
    echo ""
    echo "──────────────────────────────────────────────────────"
    echo "  Codex OAuth setup required"
    echo "  Open the URL below in any browser and follow steps."
    echo "──────────────────────────────────────────────────────"
    codex login --device-auth 2>&1 | tee -a "$HERMES_HOME/codex-login.log"
    echo "✓ Codex OAuth completed and saved to $CODEX_HOME/auth.json"
    ;;
  *)
    echo "Usage: $0 detect-or-prompt" >&2
    exit 2
    ;;
esac
