#!/usr/bin/env bats

IMAGE="paperclip-hermes-codex:test"

setup_file() {
  docker build --platform linux/amd64 -t "$IMAGE" "$BATS_TEST_DIRNAME/../.."
}
teardown_file() { docker rmi -f "$IMAGE" 2>/dev/null || true; }

@test "image: paperclipai 바이너리 존재" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "command -v paperclipai"
  [ "$status" -eq 0 ]
}

@test "image: hermes 바이너리 존재" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "command -v hermes"
  [ "$status" -eq 0 ]
}

@test "image: codex 바이너리 존재" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "command -v codex"
  [ "$status" -eq 0 ]
}

@test "image: ttyd 바이너리 존재" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "command -v ttyd"
  [ "$status" -eq 0 ]
}

@test "image: entrypoint/supervisor/codex-oauth 스크립트 실행권 있음" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "test -x /entrypoint.sh && test -x /usr/local/bin/supervisor.sh && test -x /usr/local/bin/codex-oauth.sh"
  [ "$status" -eq 0 ]
}

@test "image: /paperclip /home/node/.hermes /home/node/.codex 디렉터리 존재 + node 소유" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "stat -c '%U' /home/node/.hermes /home/node/.codex"
  [ "$status" -eq 0 ]
  [[ "$output" == *"node"* ]]
}

@test "image: 노출 포트 3100 9119 4860" {
  run docker inspect --format '{{.Config.ExposedPorts}}' "$IMAGE"
  [ "$status" -eq 0 ]
  [[ "$output" == *"3100"* ]]
  [[ "$output" == *"9119"* ]]
  [[ "$output" == *"4860"* ]]
}
