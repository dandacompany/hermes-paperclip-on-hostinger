#!/usr/bin/env bash
#
# setup.sh — interactive bootstrap for hermes-paperclip-on-hostinger.
#
# Picks an exposure mode and writes .env. Safe to re-run.
#
# Modes:
#   tailscale   — private mesh sidecar (recommended for personal+team)
#   local       — 127.0.0.1 binding only (no external access)
#   traefik     — public HTTPS via existing Traefik on this host
#   cloudflared — public HTTPS via Cloudflare Tunnel
#
# Non-interactive examples:
#   MODE=tailscale TS_AUTHKEY=tskey-auth-... ADMIN_EMAIL=you@example.com ./setup.sh
#   MODE=local ADMIN_EMAIL=you@example.com ./setup.sh
#   MODE=traefik PROJECT_DOMAIN=hermes.example.com ADMIN_EMAIL=you@example.com ./setup.sh
#   ./setup.sh --rotate    # keeps existing mode, regenerates password
#
set -euo pipefail
cd "$(dirname "$0")"

ROTATE=0
[[ "${1:-}" == "--rotate" ]] && ROTATE=1

# ── 1. deps ───────────────────────────────────────────────────
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1"; exit 1; }; }
need openssl
need docker

# ── 2. resolve MODE ──────────────────────────────────────────
if [[ $ROTATE -eq 1 ]] && [[ -f .env ]]; then
  # On rotate, keep the existing mode + domain + email.
  source .env
  MODE=$(echo "$COMPOSE_FILE" | grep -oE 'docker-compose\.(local|tailscale|traefik|cloudflared)\.yml' \
    | sed -E 's|docker-compose\.([a-z]+)\.yml|\1|')
fi

if [[ -z "${MODE:-}" ]]; then
  echo
  echo "Exposure modes:"
  echo "  tailscale   → private mesh (★ recommended for personal+team)"
  echo "  local       → 127.0.0.1 only (no external access)"
  echo "  traefik     → public HTTPS via existing Traefik on this host"
  echo "  cloudflared → public HTTPS via Cloudflare Tunnel (no inbound ports)"
  echo
  read -rp "Choose mode [tailscale]: " MODE
  MODE=${MODE:-tailscale}
fi

case "$MODE" in
  local|tailscale|traefik|cloudflared) ;;
  *) echo "Invalid MODE: $MODE"; exit 1 ;;
esac

# ── 3a. resolve PROJECT_DOMAIN (skipped in local, tailscale) ──
if [[ "$MODE" == "traefik" || "$MODE" == "cloudflared" ]] && [[ -z "${PROJECT_DOMAIN:-}" ]]; then
  read -rp "Public DNS suffix (e.g. hermes.example.com): " PROJECT_DOMAIN
  if [[ -z "$PROJECT_DOMAIN" ]]; then
    echo "PROJECT_DOMAIN is required for mode=$MODE"; exit 1
  fi
fi
PROJECT_DOMAIN=${PROJECT_DOMAIN:-localhost}

# ── 3b. resolve TS_AUTHKEY + TS_HOSTNAME (tailscale only) ────
if [[ "$MODE" == "tailscale" ]]; then
  if [[ -z "${TS_AUTHKEY:-}" ]]; then
    echo
    echo "Tailscale auth key needed. Generate one at:"
    echo "  https://login.tailscale.com/admin/settings/keys"
    echo "  (reusable = OK, ephemeral = your call, expiry = your call)"
    read -rp "TS_AUTHKEY (tskey-auth-...): " TS_AUTHKEY
    if [[ -z "$TS_AUTHKEY" ]]; then
      echo "TS_AUTHKEY is required for mode=tailscale"; exit 1
    fi
  fi
  TS_HOSTNAME=${TS_HOSTNAME:-${COMPOSE_PROJECT_NAME:-hermes-paperclip}}
fi

# ── 4. resolve ADMIN_EMAIL (Paperclip bootstrap requires it) ──
if [[ -z "${ADMIN_EMAIL:-}" ]]; then
  read -rp "Admin email (Paperclip bootstrap): " ADMIN_EMAIL
  if [[ -z "$ADMIN_EMAIL" ]]; then
    echo "ADMIN_EMAIL is required"; exit 1
  fi
fi

# ── 5. generate password ─────────────────────────────────────
ADMIN_USERNAME=${ADMIN_USERNAME:-hermes}
ADMIN_NAME=${ADMIN_NAME:-Dante}
ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)

# ── 6. compute COMPOSE_FILE + PAPERCLIP_PUBLIC_URL by mode ───
case "$MODE" in
  local)
    COMPOSE_FILE_VAL="docker-compose.yml:docker-compose.local.yml"
    PUBLIC_URL_VAL="http://localhost:3100"
    TUI_URL="http://127.0.0.1:4860"
    DASH_URL="http://127.0.0.1:9119"
    PAPER_URL="http://127.0.0.1:3100"
    ;;
  tailscale)
    COMPOSE_FILE_VAL="docker-compose.yml:docker-compose.tailscale.yml"
    # PUBLIC_URL points at the mesh hostname; Tailscale will issue the
    # actual cert once the sidecar joins, and your tailnet domain will
    # be visible in the Tailscale admin console.
    PUBLIC_URL_VAL="https://${TS_HOSTNAME}.<your-tailnet>.ts.net:3100"
    TUI_URL="https://${TS_HOSTNAME}.<your-tailnet>.ts.net:4860  (mesh)  |  http://127.0.0.1:4860  (this host)"
    DASH_URL="https://${TS_HOSTNAME}.<your-tailnet>.ts.net:9119  (mesh)  |  http://127.0.0.1:9119  (this host)"
    PAPER_URL="https://${TS_HOSTNAME}.<your-tailnet>.ts.net:3100  (mesh)  |  http://127.0.0.1:3100  (this host)"
    ;;
  traefik)
    COMPOSE_FILE_VAL="docker-compose.yml:docker-compose.traefik.yml"
    PUBLIC_URL_VAL="https://paperclip.${PROJECT_DOMAIN}"
    TUI_URL="https://tui.${PROJECT_DOMAIN}"
    DASH_URL="https://dash.${PROJECT_DOMAIN}"
    PAPER_URL="https://paperclip.${PROJECT_DOMAIN}"
    ;;
  cloudflared)
    COMPOSE_FILE_VAL="docker-compose.yml:docker-compose.cloudflared.yml"
    PUBLIC_URL_VAL="https://paperclip.${PROJECT_DOMAIN}"
    TUI_URL="https://tui.${PROJECT_DOMAIN}"
    DASH_URL="https://dash.${PROJECT_DOMAIN}"
    PAPER_URL="https://paperclip.${PROJECT_DOMAIN}"
    ;;
esac

# ── 7. write .env (back up existing) ─────────────────────────
[[ -f .env ]] && cp .env ".env.bak-$(date +%Y%m%d-%H%M%S)"

{
  echo "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-hermes-paperclip}"
  echo "COMPOSE_FILE=${COMPOSE_FILE_VAL}"
  echo "PROJECT_DOMAIN=${PROJECT_DOMAIN}"
  echo "ADMIN_USERNAME=${ADMIN_USERNAME}"
  echo "ADMIN_NAME=${ADMIN_NAME}"
  echo "ADMIN_EMAIL=${ADMIN_EMAIL}"
  echo "ADMIN_PASSWORD=${ADMIN_PASSWORD}"
  echo "PAPERCLIP_PUBLIC_URL=${PUBLIC_URL_VAL}"
  if [[ "$MODE" == "tailscale" ]]; then
    echo "TS_AUTHKEY=${TS_AUTHKEY}"
    echo "TS_HOSTNAME=${TS_HOSTNAME}"
  fi
} > .env
chmod 600 .env

# ── 8. report ────────────────────────────────────────────────
cat <<EOF

  hermes-paperclip-on-hostinger is configured (mode=${MODE}).

  URLs:
    Hermes TUI       : ${TUI_URL}
    Hermes Dashboard : ${DASH_URL}
    Paperclip        : ${PAPER_URL}

  Credentials (Hermes ttyd + Paperclip admin):
    username : ${ADMIN_USERNAME}     (Hermes TUI)
    email    : ${ADMIN_EMAIL}        (Paperclip login)
    password : ${ADMIN_PASSWORD}
    ↑ save it; .env is chmod 600. Rotate later with: ./setup.sh --rotate

EOF

case "$MODE" in
  local)
    cat <<EOF
  Next:
    docker compose up -d

  Notes:
    Ports bind to 127.0.0.1 only — your LAN cannot reach the stack.
    For external (mesh) access, re-run setup.sh and pick tailscale.
EOF
    ;;
  tailscale)
    cat <<EOF
  Next:
    docker compose up -d

  After boot:
    1. This host accesses containers via 127.0.0.1 (above URLs).
    2. The Tailscale sidecar registers as '${TS_HOSTNAME}' in your tailnet.
    3. Check https://login.tailscale.com/admin/machines for its full
       <hostname>.<tailnet>.ts.net domain (replace the placeholder above).
    4. Other mesh members (your phone, teammates) reach the stack via
       https://<TS_HOSTNAME>.<your-tailnet>.ts.net:{9119,4860,3100}/
       with Tailscale running on their device — no public DNS or
       Let's Encrypt rate limits in play.

  Notes:
    - The host running this stack does NOT need Tailscale installed.
      It accesses its own containers via 127.0.0.1.
    - To share access, just invite teammates to your tailnet and
      they'll see this machine in their device list.
    - To stop sharing externally: docker compose stop tailscale
      (the rest of the stack keeps running on 127.0.0.1).
EOF
    ;;
  traefik)
    cat <<EOF
  DNS records you need (A or CNAME → this VPS public IP):
    tui.${PROJECT_DOMAIN}
    dash.${PROJECT_DOMAIN}
    paperclip.${PROJECT_DOMAIN}

  Next:
    docker compose up -d
EOF
    ;;
  cloudflared)
    cat <<EOF
  Cloudflare Tunnel setup (one-time, on your machine):
    cloudflared tunnel login
    cloudflared tunnel create ${COMPOSE_PROJECT_NAME:-hermes-paperclip}
    cp ~/.cloudflared/<UUID>.json ./cloudflared/
    cp cloudflared/config.yml.example cloudflared/config.yml
    # edit cloudflared/config.yml: set tunnel UUID + hostnames
    cloudflared tunnel route dns ${COMPOSE_PROJECT_NAME:-hermes-paperclip} tui.${PROJECT_DOMAIN}
    cloudflared tunnel route dns ${COMPOSE_PROJECT_NAME:-hermes-paperclip} dash.${PROJECT_DOMAIN}
    cloudflared tunnel route dns ${COMPOSE_PROJECT_NAME:-hermes-paperclip} paperclip.${PROJECT_DOMAIN}

  Next:
    docker compose up -d

  See docs/EXPOSURE-cloudflared.md for the full walkthrough.
EOF
    ;;
esac
