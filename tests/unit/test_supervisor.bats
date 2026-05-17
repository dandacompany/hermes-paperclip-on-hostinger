#!/usr/bin/env bats
load '../helpers/bats_helpers'

setup() {
  setup_tmp_home
  mkdir -p "$TMP_HOME/bin"
  SCRIPT="$BATS_TEST_DIRNAME/../../scripts/supervisor.sh"
  # mock: paperclipai exits 0 immediately (so supervisor returns)
  mock_bin paperclipai ''
  # mock: hermes ttyd 둘 다 즉시 exit 0
  mock_bin hermes ''
  mock_bin ttyd ''
  echo "u:p" > "$HERMES_HOME/.ttyd-creds"
}
teardown() { teardown_tmp_home; }

@test "supervisor: paperclipai foreground 호출 + BG 2개 spawn" {
  run timeout 5 bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"hermes-dashboard spawned"* ]]
  [[ "$output" == *"hermes-ttyd spawned"* ]]
}

@test "supervisor: .ttyd-creds 누락 시 명시적 에러" {
  rm "$HERMES_HOME/.ttyd-creds"
  run timeout 5 bash "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" == *".ttyd-creds not found"* ]]
}
