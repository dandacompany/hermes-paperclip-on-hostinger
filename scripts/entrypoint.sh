#!/bin/bash
set -eu

export HERMES_HOME="${HERMES_HOME:-/home/node/.hermes}"
export CODEX_HOME="${CODEX_HOME:-/home/node/.codex}"
export PAPERCLIP_HOME="${PAPERCLIP_HOME:-/paperclip}"
ETC_HERMES="${ETC_HERMES:-/etc/hermes}"
PORT="${PORT:-3100}"
TEST_MODE="${TEST_MODE:-}"
MACHINE_ID="${TEST_MACHINE_ID:-$(cat /etc/machine-id 2>/dev/null || echo default-machine)}"

# ── [1] permission fix ──
if [ -z "$TEST_MODE" ]; then
  sudo chown -R node:node "$PAPERCLIP_HOME" "$HERMES_HOME" "$CODEX_HOME"
fi

# ── [2] Paperclip bootstrap ──
bootstrap_paperclip() {
  local config="$PAPERCLIP_HOME/instances/default/config.json"
  [ -f "$config" ] && return 0
  echo "→ Paperclip first-run bootstrap"
  PAPERCLIP_PUBLIC_URL="http://localhost:$PORT" \
  PAPERCLIP_ALLOWED_HOSTNAMES="localhost:$PORT,${PAPERCLIP_ALLOWED_HOSTNAMES:-}" \
    paperclipai onboard --yes --bind lan --run &
  local pid=$!
  until curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; do sleep 2; done
  _paperclip_admin_signup
  jq '.auth.disableSignUp = true' "$config" > "$config.tmp" && mv "$config.tmp" "$config"
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

_paperclip_admin_signup() {
  local cookies
  cookies=$(mktemp)

  local signup_payload signin_payload accept_payload
  signup_payload=$(jq -n \
    --arg name     "$ADMIN_NAME" \
    --arg email    "$ADMIN_EMAIL" \
    --arg password "$ADMIN_PASSWORD" \
    '{name: $name, email: $email, password: $password}')
  signin_payload=$(jq -n \
    --arg email    "$ADMIN_EMAIL" \
    --arg password "$ADMIN_PASSWORD" \
    '{email: $email, password: $password}')
  accept_payload='{"requestType":"human"}'

  curl -sS -c "$cookies" -b "$cookies" \
    -H "Content-Type: application/json" -H "Origin: http://localhost:$PORT" \
    -X POST "http://localhost:$PORT/api/auth/sign-up/email" \
    --data "$signup_payload"
  curl -sS -c "$cookies" -b "$cookies" \
    -H "Content-Type: application/json" -H "Origin: http://localhost:$PORT" \
    -X POST "http://localhost:$PORT/api/auth/sign-in/email" \
    --data "$signin_payload"
  local invite
  invite=$(paperclipai auth bootstrap-ceo --force | grep 'Invite URL' | awk -F'/invite/' '{print $2}')
  curl -sS -c "$cookies" -b "$cookies" \
    -H "Content-Type: application/json" -H "Origin: http://localhost:$PORT" \
    -X POST "http://localhost:$PORT/api/invites/$invite/accept" \
    --data "$accept_payload"

  rm -f "$cookies"
}

# ── [3] Hermes bootstrap ──
bootstrap_hermes() {
  [ -f "$HERMES_HOME/config.yaml" ] && return 0
  echo "→ Hermes first-run bootstrap"
  cp -r "$ETC_HERMES/template/." "$HERMES_HOME/"
  if [ -z "$TEST_MODE" ]; then
    yq -i '.providers.default = "codex_local"' "$HERMES_HOME/config.yaml"
  else
    echo "providers: { default: codex_local }" >> "$HERMES_HOME/config.yaml"
  fi
  local token
  token=$(printf '%s' "$ADMIN_USERNAME:$ADMIN_PASSWORD:$MACHINE_ID" | sha256sum | cut -d' ' -f1)
  echo "session_token: $token" >> "$HERMES_HOME/config.yaml"
  echo "$ADMIN_USERNAME:$ADMIN_PASSWORD" > "$HERMES_HOME/.ttyd-creds"
  chmod 600 "$HERMES_HOME/.ttyd-creds"
}

# ── [4] Codex auth detection (non-blocking) ──
launch_codex_detection() {
  /usr/local/bin/codex-oauth.sh detect-or-prompt &
}

# ── Dispatcher ──
case "$TEST_MODE" in
  hermes-only)
    bootstrap_hermes
    exit 0
    ;;
  "")
    bootstrap_paperclip
    bootstrap_hermes
    launch_codex_detection
    exec /usr/local/bin/supervisor.sh
    ;;
  *)
    echo "unknown TEST_MODE: $TEST_MODE" >&2
    exit 2
    ;;
esac
