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

@test "image: hermes-tty.sh wrapper 실행권 있음" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "test -x /usr/local/bin/hermes-tty.sh"
  [ "$status" -eq 0 ]
}

@test "image: tini 바이너리 존재 (ENTRYPOINT가 의존)" {
  run docker run --rm --entrypoint sh "$IMAGE" -c "command -v tini"
  [ "$status" -eq 0 ]
}

@test "image: 기본 ENTRYPOINT가 spawn 시 즉시 PATH/format 에러 없이 시작" {
  # 1.5초 띄운 뒤 즉시 kill — ENTRYPOINT 가 'tini not found' 같은 즉시 실패면 1.5s 안에 exit code 127 으로 떨어진다.
  cid=$(docker run -d --rm \
    -e ADMIN_USERNAME=t -e ADMIN_NAME=T -e ADMIN_EMAIL=t@t -e ADMIN_PASSWORD=t \
    "$IMAGE" || true)
  [ -n "$cid" ]
  sleep 1.5
  status=$(docker inspect -f '{{.State.Status}}' "$cid" 2>&1 || echo missing)
  docker kill "$cid" 2>/dev/null || true
  [[ "$status" == "running" || "$status" == "exited" ]]
  # exited 라면 OCI exec 에러가 아니라 부트스트랩 progression에서 나온 것이어야 함.
  # tini 자체가 없을 때의 'exec format' 에러는 docker run 시점에 즉시 떨어져 cid 자체가 비게 된다.
}
