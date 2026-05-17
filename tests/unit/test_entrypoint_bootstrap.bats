#!/usr/bin/env bats
load '../helpers/bats_helpers'

setup() {
  setup_tmp_home
  mkdir -p "$TMP_HOME/bin" "$TMP_HOME/etc/hermes/template"
  echo "provider: placeholder" > "$TMP_HOME/etc/hermes/template/config.yaml"
  export ETC_HERMES="$TMP_HOME/etc/hermes"
  export ADMIN_USERNAME="testuser"
  export ADMIN_PASSWORD="testpw"
  export TEST_MACHINE_ID="abc123"
  # mock paperclipai/sudo/curl/yq/codex-oauth.sh to isolate entrypoint body
  mock_bin sudo 'noop'
  mock_bin yq 'mocked'
  mock_bin sha256sum 'echo "deadbeef0123 -"'
  SCRIPT="$BATS_TEST_DIRNAME/../../scripts/entrypoint.sh"
}
teardown() { teardown_tmp_home; }

@test "hermes bootstrap: config.yaml 없으면 template 복사 + provider 설정 + ttyd-creds 작성" {
  # Skip Paperclip branch — pre-create config.json
  mkdir -p "$TMP_HOME/paperclip/instances/default"
  echo "{}" > "$TMP_HOME/paperclip/instances/default/config.json"
  export PAPERCLIP_HOME="$TMP_HOME/paperclip"

  # Run only hermes bootstrap branch
  TEST_MODE=hermes-only run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$HERMES_HOME/config.yaml" ]
  [ -f "$HERMES_HOME/.ttyd-creds" ]
  grep -q "testuser:testpw" "$HERMES_HOME/.ttyd-creds"
  grep -q "session_token:" "$HERMES_HOME/config.yaml"
}

@test "hermes bootstrap: 이미 config.yaml 있으면 건드리지 않음" {
  echo "preserved: true" > "$HERMES_HOME/config.yaml"
  mkdir -p "$TMP_HOME/paperclip/instances/default"
  echo "{}" > "$TMP_HOME/paperclip/instances/default/config.json"
  export PAPERCLIP_HOME="$TMP_HOME/paperclip"

  TEST_MODE=hermes-only run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "preserved: true" "$HERMES_HOME/config.yaml"
}
