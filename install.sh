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
echo
echo "Done. Tail logs with: (cd $PWD && docker compose logs -f)"
