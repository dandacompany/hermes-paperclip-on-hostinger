#!/usr/bin/env bash
#
# refresh-tailnet.sh — refresh PAPERCLIP_PUBLIC_URL with the live
# Tailscale FQDN and restart paperclip. Run this if install.sh's
# auto-detect failed (sidecar slow to register, network hiccup, etc.)
# or if your tailnet name changed.
#
set -euo pipefail
cd "$(dirname "$0")/.."

if ! grep -q "docker-compose.tailscale.yml" .env 2>/dev/null; then
  echo "Not in tailscale mode (check .env COMPOSE_FILE). Exiting."
  exit 1
fi

FQDN=$(docker compose exec -T tailscale sh -c 'tailscale status --json' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Self']['DNSName'].rstrip('.'))")

if [ -z "$FQDN" ]; then
  echo "Could not read tailnet FQDN from sidecar. Is it running?"
  docker compose ps tailscale
  exit 1
fi

echo "==> tailnet FQDN: $FQDN"
sed -i.bak "s|^PAPERCLIP_PUBLIC_URL=.*|PAPERCLIP_PUBLIC_URL=https://${FQDN}:3100|" .env && rm .env.bak
echo "==> PAPERCLIP_PUBLIC_URL updated"
grep "^PAPERCLIP_PUBLIC_URL=" .env
echo "==> restarting paperclip"
docker compose up -d paperclip
echo "==> done. Mesh access:"
echo "    Dashboard : https://${FQDN}:9119"
echo "    TUI       : https://${FQDN}:4860"
echo "    Paperclip : https://${FQDN}:3100"
