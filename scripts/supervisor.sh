#!/bin/bash
set -eu

CREDS_FILE="${HERMES_HOME}/.ttyd-creds"
if [ ! -f "$CREDS_FILE" ]; then
  echo "✗ $CREDS_FILE not found (Hermes bootstrap incomplete)" >&2
  exit 1
fi
HERMES_CREDS=$(cat "$CREDS_FILE")

spawn_bg() {
  local name="$1"; shift
  echo "→ $name spawned (pid=$$)"
  (
    retries=0
    while [ "$retries" -lt 3 ]; do
      "$@" || true
      retries=$((retries+1))
      echo "✗ $name exited (attempt $retries/3)" >&2
      sleep 2
    done
    echo "✗ $name failed 3 times, giving up" >&2
  ) &
}

spawn_bg "hermes-dashboard" hermes dashboard --port 9119 --host 0.0.0.0 --insecure --no-open --skip-build
spawn_bg "hermes-ttyd"      ttyd -p 4860 -c "$HERMES_CREDS" hermes shell

exec paperclipai run
