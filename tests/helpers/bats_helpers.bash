#!/usr/bin/env bash
# Common BATS helpers: temporary home directory, env initialization, mock binaries

setup_tmp_home() {
  TMP_HOME=$(mktemp -d)
  export HOME="$TMP_HOME"
  export HERMES_HOME="$TMP_HOME/.hermes"
  export CODEX_HOME="$TMP_HOME/.codex"
  mkdir -p "$HERMES_HOME" "$CODEX_HOME"
}

teardown_tmp_home() {
  rm -rf "$TMP_HOME"
}

mock_bin() {
  local name="$1"
  shift
  mkdir -p "$TMP_HOME/bin"
  cat > "$TMP_HOME/bin/$name" <<EOF
#!/bin/bash
echo "\$@"
EOF
  chmod +x "$TMP_HOME/bin/$name"
  export PATH="$TMP_HOME/bin:$PATH"
}
