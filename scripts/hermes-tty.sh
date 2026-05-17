#!/bin/bash
# ttyd entry point — start an interactive hermes shell session,
# fall back to bash if hermes exits.

set -u
export HERMES_HOME="${HERMES_HOME:-/home/node/.hermes}"
export HOME="${HOME:-/home/node}"

# First-run safety: if config.yaml is missing, drop to bash so the user can
# inspect why. entrypoint.sh is supposed to create config.yaml at boot.
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
  echo "✗ $HERMES_HOME/config.yaml missing — bootstrap incomplete." >&2
  exec bash
fi

trap 'echo; echo "Exiting hermes — dropping to bash..."; exec bash' INT
hermes || true
exec bash
