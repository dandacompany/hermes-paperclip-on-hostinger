#!/bin/bash
set -eu

MODE="${MODE:-local}"
case "$MODE" in
  local|tailscale) ;;
  *) echo "MODE must be local | tailscale" >&2; exit 1 ;;
esac

if [ ! -f .env ]; then
  cp .env.example .env
fi

case "$MODE" in
  local)
    sed -i.bak 's|^COMPOSE_FILE=.*|COMPOSE_FILE=docker-compose.yml:docker-compose.local.yml|' .env
    rm -f .env.bak
    echo "-> MODE=local set. Run: docker compose up -d"
    ;;
  tailscale)
    if [ -z "${TS_AUTHKEY:-}" ]; then
      echo "x TS_AUTHKEY env var required for tailscale mode" >&2
      exit 1
    fi
    sed -i.bak 's|^COMPOSE_FILE=.*|COMPOSE_FILE=docker-compose.yml:docker-compose.tailscale.yml|' .env
    sed -i.bak "s|^TS_AUTHKEY=.*|TS_AUTHKEY=$TS_AUTHKEY|" .env
    sed -i.bak "s|^TS_HOSTNAME=.*|TS_HOSTNAME=${TS_HOSTNAME:-paperclip}|" .env
    sed -i.bak "s|^PAPERCLIP_PUBLIC_URL=.*|PAPERCLIP_PUBLIC_URL=https://${TS_HOSTNAME:-paperclip}.ts.net:3100|" .env
    rm -f .env.bak
    echo "-> MODE=tailscale set. Run: docker compose up -d"
    ;;
esac

# ADMIN_PASSWORD가 비어 있으면 랜덤 32자 생성
if grep -q '^ADMIN_PASSWORD=$' .env; then
  PW=$(openssl rand -hex 16)
  sed -i.bak "s|^ADMIN_PASSWORD=$|ADMIN_PASSWORD=$PW|" .env
  rm -f .env.bak
  echo "-> ADMIN_PASSWORD generated (saved in .env)"
fi
