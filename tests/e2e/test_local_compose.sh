#!/bin/bash
# Local-mode E2E smoke for paperclip-hermes-codex.
# Brings up the container with docker-compose.yml + docker-compose.local.yml,
# verifies paperclip/health, hermes dashboard, ttyd basic-auth, and that
# Codex auth detection ran (no actual OAuth — just the log line).
set -eu

PROJECT="paperclip-hermes-codex-e2e"
export COMPOSE_FILE="docker-compose.yml:docker-compose.local.yml"
export ADMIN_USERNAME="${ADMIN_USERNAME:-e2euser}"
export ADMIN_NAME="${ADMIN_NAME:-E2E}"
export ADMIN_EMAIL="${ADMIN_EMAIL:-e2e@example.com}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-e2e-$(openssl rand -hex 8)}"

cleanup() {
  echo "→ Cleaning up..."
  docker compose -p "$PROJECT" down -v --remove-orphans 2>&1 | tail -3 || true
}
trap cleanup EXIT

echo "→ Bringing up $PROJECT..."
docker compose -p "$PROJECT" up -d

echo "→ Waiting up to 120s for paperclip /api/health..."
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:3100/api/health > /dev/null; then break; fi
  sleep 2
done
curl -sf http://127.0.0.1:3100/api/health
echo "  ✓ paperclip /api/health OK"

echo "→ Checking hermes dashboard..."
curl -sfI http://127.0.0.1:9119/ | head -1 | grep -qE '200|301|302'
echo "  ✓ hermes dashboard responds"

echo "→ Checking ttyd basic-auth..."
curl -sfI -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" http://127.0.0.1:4860/ | head -1 | grep -q '200'
echo "  ✓ ttyd basic-auth OK"

echo "→ Checking Codex auth detection log..."
docker compose -p "$PROJECT" logs paperclip-hermes-codex | grep -E "Codex (OAuth setup required|auth:)"
echo "  ✓ Codex auth detection ran"

echo
echo "✓ ALL E2E CHECKS PASSED"
