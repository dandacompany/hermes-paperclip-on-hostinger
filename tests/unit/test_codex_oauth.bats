#!/usr/bin/env bats
load '../helpers/bats_helpers'

setup() {
  setup_tmp_home
  mkdir -p "$TMP_HOME/bin"
  mock_bin codex 'login --device-auth'   # mock codex CLI
  SCRIPT="$BATS_TEST_DIRNAME/../../scripts/codex-oauth.sh"
}
teardown() { teardown_tmp_home; }

@test "detect-or-prompt: auth.json 있으면 mode 출력 후 exit 0" {
  echo '{"mode":"OAuth"}' > "$CODEX_HOME/auth.json"
  run bash "$SCRIPT" detect-or-prompt
  [ "$status" -eq 0 ]
  [[ "$output" == *"Codex auth: OAuth"* ]]
}

@test "detect-or-prompt: OPENAI_API_KEY 있고 auth.json 없으면 API key 모드 안내" {
  export OPENAI_API_KEY="sk-test"
  run bash "$SCRIPT" detect-or-prompt
  [ "$status" -eq 0 ]
  [[ "$output" == *"Codex auth: API key"* ]]
}

@test "detect-or-prompt: 둘 다 없으면 codex login --device-auth 호출" {
  unset OPENAI_API_KEY
  run bash "$SCRIPT" detect-or-prompt
  [ "$status" -eq 0 ]
  [[ "$output" == *"login --device-auth"* ]]
}
