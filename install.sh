#!/usr/bin/env bash
#
# install.sh — one-line installer for hermes-paperclip-on-hostinger.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/install.sh \
#     | MODE=local bash
#   curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/install.sh \
#     | MODE=traefik PROJECT_DOMAIN=hermes.example.com ADMIN_EMAIL=you@example.com bash
#
set -euo pipefail

REPO_URL=${REPO_URL:-https://github.com/dandacompany/hermes-paperclip-on-hostinger.git}
INSTALL_DIR=${INSTALL_DIR:-hermes-paperclip-on-hostinger}
BRANCH=${BRANCH:-main}

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "==> updating existing checkout in $INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  echo "==> cloning $REPO_URL → $INSTALL_DIR"
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
./setup.sh

echo "==> starting compose stack"
docker compose up -d

# ── Tailscale post-boot: rewrite PAPERCLIP_PUBLIC_URL with the real
#    <hostname>.<tailnet>.ts.net once the sidecar has joined. This
#    avoids a chicken-and-egg problem where the sidecar needs the
#    auth key to find out its tailnet name, but Paperclip needs that
#    URL at its own boot time.
if grep -q "docker-compose.tailscale.yml" .env 2>/dev/null; then
  echo "==> waiting for Tailscale sidecar to register..."
  for _ in $(seq 1 30); do
    FQDN=$(docker compose exec -T tailscale sh -c 'tailscale status --json 2>/dev/null' \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null || true)
    [ -n "$FQDN" ] && break
    sleep 2
  done
  if [ -n "$FQDN" ]; then
    echo "==> tailnet FQDN: $FQDN"
    sed -i.bak "s|^PAPERCLIP_PUBLIC_URL=.*|PAPERCLIP_PUBLIC_URL=https://${FQDN}:3100|" .env && rm .env.bak
    echo "==> restarting paperclip with mesh PUBLIC_URL"
    docker compose up -d paperclip >/dev/null 2>&1
  else
    echo "==> WARN: could not determine tailnet FQDN within 60s."
    echo "    Run later: ./scripts/refresh-tailnet.sh"
  fi
fi

echo
echo "Done. Tail logs with: (cd $PWD && docker compose logs -f)"
