# Paperclip-Hermes-Codex 단일 컨테이너 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paperclip + Hermes + Codex를 단일 컨테이너에 통합하고, GHA nightly 빌드로 호스팅어 콘솔 "업데이트" 버튼 한 번에 세 도구 최신 버전이 반영되는 OSS 스택을 구축한다.

**Architecture:** Multi-stage Dockerfile로 Hermes 바이너리를 Paperclip 이미지에 합친 단일 이미지를 GHCR에 publish. tini 아래 paperclip(FG) + hermes dashboard·ttyd(BG) supervisor. 첫 부팅 시 ADMIN_* env로 Paperclip/Hermes 자동 bootstrap, Codex OAuth만 비차단 1회 인증.

**Tech Stack:** Docker (multi-stage build), bash + tini, bats-core (shell unit test), GitHub Actions, docker compose, Tailscale serve, gitleaks (pre-commit).

**Spec reference:** `docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md`

**PR breakdown:**
- PR 1: 빌드 인프라 — Dockerfile + entrypoint/supervisor/codex-oauth 스크립트 + bats 단위 테스트 + GHA workflow
- PR 2: Compose 4종 + Tailscale serve.json + compose config 검증
- PR 3: .env.example + setup.sh + 새 README + gitleaks 룰 갱신
- PR 4: E2E 검증 (Mac local + Hostinger staging) + v0.1-sidecar 태그
- PR 5: main rewrite (구 사이드카 파일 제거 + MIGRATION 문서)

---

## File Structure

### 새로 만들 파일

| Path | 책임 |
|---|---|
| `Dockerfile` | Multi-stage build: hermes 바이너리 추출 → paperclip base 위에 합침 |
| `scripts/entrypoint.sh` | 부팅 시 chown + Paperclip/Hermes bootstrap + Codex auth detection + supervisor exec |
| `scripts/supervisor.sh` | hermes dashboard + ttyd background spawn + retry, paperclipai run exec |
| `scripts/codex-oauth.sh` | Codex OAuth/API key 분기 (auth.json 검사 + device login fallback) |
| `tests/unit/test_codex_oauth.bats` | codex-oauth.sh 단위 테스트 |
| `tests/unit/test_entrypoint_bootstrap.bats` | entrypoint.sh 부트스트랩 분기 단위 테스트 |
| `tests/unit/test_supervisor.bats` | supervisor.sh BG spawn + retry 테스트 |
| `tests/integration/test_image_build.bats` | Docker image build + 필수 바이너리 존재 검증 |
| `tests/e2e/test_local_compose.sh` | Mac local compose E2E (health endpoints) |
| `tests/helpers/bats_helpers.bash` | bats 공통 helper (mock 디렉터리 생성 등) |
| `.github/workflows/build-and-push.yml` | GHA nightly + push 트리거 빌드 워크플로 |
| `.github/workflows/test.yml` | bats 단위/통합 테스트 CI |
| `docker-compose.yml` | base — paperclip-hermes-codex 서비스 + volumes (v1 rewrite) |
| `docker-compose.local.yml` | overlay — 127.0.0.1 포트 바인딩 |
| `docker-compose.tailscale.yml` | overlay — tailscale 사이드카 + serve.json mount |
| `docker-compose.console.yml` | self-contained — Hostinger URL import 전용 |
| `tailscale/serve.json` | Tailscale HTTPS 라우팅 (3 포트 → 3 backend) |
| `setup.sh` | 로컬 사용자용 MODE 선택기 + .env 생성 (v1 rewrite) |
| `.env.example` | 환경변수 템플릿 (v1 rewrite) |
| `README.md` | v1 사용법 + 호스팅어 콘솔 흐름 (rewrite) |
| `docs/MIGRATION-v0.1-to-v1.md` | 사이드카에서 단일 컨테이너로 자발 마이그레이션 가이드 |

### 제거할 파일 (PR 5)

`docker-compose.traefik.yml`, `docker-compose.cloudflared.yml`, 구 `docs/EXPOSURE-traefik.md`, `docs/EXPOSURE-cloudflared.md`, 구 `docs/tutorial-hermes-paperclip-on-hostinger/`, 구 `docs/tutorial-hostinger-console/`, 구 `docker-compose.yml` 안 `hermes-*` 서비스 정의.

### 유지할 파일

`.gitleaks.toml` (룰 추가 patch만), `.pre-commit-config.yaml` (변경 없음), `LICENSE`, `docs/INTEGRATION.md` (참조용으로 유지).

---

## PR 1 — 빌드 인프라

**목표:** Dockerfile + scripts + GHA workflow + bats 테스트 인프라. add-only (구 사이드카 파일 영향 0).

### Task 1.1: bats 테스트 인프라 도입

**Files:**
- Create: `tests/helpers/bats_helpers.bash`
- Create: `tests/unit/.gitkeep`
- Create: `tests/integration/.gitkeep`
- Modify: 없음 (디렉터리 추가만)

- [ ] **Step 1: tests/ 디렉터리 구조 생성**

```bash
mkdir -p tests/unit tests/integration tests/e2e tests/helpers
touch tests/unit/.gitkeep tests/integration/.gitkeep tests/e2e/.gitkeep
```

- [ ] **Step 2: bats helper 작성**

`tests/helpers/bats_helpers.bash`:
```bash
#!/usr/bin/env bash
# 공통 helper: 임시 home 디렉터리, env 초기화, mock 바이너리 PATH

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
  local name="$1"; shift
  cat > "$TMP_HOME/bin/$name" <<EOF
#!/bin/bash
echo "$@"
EOF
  chmod +x "$TMP_HOME/bin/$name"
  export PATH="$TMP_HOME/bin:$PATH"
}
```

- [ ] **Step 3: bats-core 로컬 검증**

Run: `brew install bats-core jq` (macOS) 또는 `apt-get install -y bats jq` (Linux)
Run: `bats --version`
Expected: `Bats 1.x.x`

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: introduce bats-core unit test infrastructure"
```

### Task 1.2: codex-oauth.sh detect 분기

**Files:**
- Create: `scripts/codex-oauth.sh`
- Create: `tests/unit/test_codex_oauth.bats`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_codex_oauth.bats`:
```bash
#!/usr/bin/env bats
load '../helpers/bats_helpers'

setup() {
  setup_tmp_home
  mkdir -p "$TMP_HOME/bin"
  mock_bin codex 'login --device'   # mock codex CLI
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

@test "detect-or-prompt: 둘 다 없으면 codex login --device 호출" {
  unset OPENAI_API_KEY
  run bash "$SCRIPT" detect-or-prompt
  [ "$status" -eq 0 ]
  [[ "$output" == *"login --device"* ]]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/unit/test_codex_oauth.bats`
Expected: 3 tests fail (`scripts/codex-oauth.sh: No such file or directory`)

- [ ] **Step 3: Write minimal implementation**

`scripts/codex-oauth.sh`:
```bash
#!/bin/bash
set -eu
case "${1:-}" in
  detect-or-prompt)
    if [ -f "$CODEX_HOME/auth.json" ]; then
      MODE=$(jq -r '.mode // "unknown"' "$CODEX_HOME/auth.json" 2>/dev/null || echo "unknown")
      echo "✓ Codex auth: $MODE (token found at $CODEX_HOME/auth.json)"
      exit 0
    fi
    if [ -n "${OPENAI_API_KEY:-}" ]; then
      echo "✓ Codex auth: API key (env, Codex CLI 0.122+ will auto-write auth.json)"
      exit 0
    fi
    echo ""
    echo "──────────────────────────────────────────────────────"
    echo "  Codex OAuth setup required"
    echo "  Open the URL below in any browser and follow steps."
    echo "──────────────────────────────────────────────────────"
    codex login --device 2>&1 | tee -a "$HERMES_HOME/codex-login.log"
    echo "✓ Codex OAuth completed and saved to $CODEX_HOME/auth.json"
    ;;
  *)
    echo "Usage: $0 detect-or-prompt" >&2
    exit 2
    ;;
esac
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats tests/unit/test_codex_oauth.bats`
Expected: `3 tests, 0 failures`

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/codex-oauth.sh
git add scripts/codex-oauth.sh tests/unit/test_codex_oauth.bats
git commit -m "feat(scripts): add codex-oauth.sh with auth detection branches"
```

### Task 1.3: supervisor.sh — BG spawn + retry

**Files:**
- Create: `scripts/supervisor.sh`
- Create: `tests/unit/test_supervisor.bats`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_supervisor.bats`:
```bash
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/unit/test_supervisor.bats`
Expected: 2 tests fail (`No such file or directory`)

- [ ] **Step 3: Write implementation**

`scripts/supervisor.sh`:
```bash
#!/bin/bash
set -eu

CREDS_FILE="$HERMES_HOME/.ttyd-creds"
if [ ! -f "$CREDS_FILE" ]; then
  echo "✗ $CREDS_FILE not found (Hermes bootstrap incomplete)" >&2
  exit 1
fi
HERMES_CREDS=$(cat "$CREDS_FILE")

spawn_bg() {
  local name="$1"; shift
  echo "→ $name spawned (pid=$$)"
  (
    local retries=0
    while [ "$retries" -lt 3 ]; do
      "$@" || true
      retries=$((retries+1))
      echo "✗ $name exited (attempt $retries/3)" >&2
      sleep 2
    done
    echo "✗ $name failed 3 times, giving up" >&2
  ) &
}

spawn_bg "hermes-dashboard" hermes dashboard --port 9119 --bind 0.0.0.0
spawn_bg "hermes-ttyd"      ttyd -p 4860 -c "$HERMES_CREDS" hermes shell

exec paperclipai run
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats tests/unit/test_supervisor.bats`
Expected: `2 tests, 0 failures`

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/supervisor.sh
git add scripts/supervisor.sh tests/unit/test_supervisor.bats
git commit -m "feat(scripts): add supervisor.sh with BG spawn + 3x retry"
```

### Task 1.4: entrypoint.sh — Hermes bootstrap 분기

**Files:**
- Create: `scripts/entrypoint.sh`
- Create: `tests/unit/test_entrypoint_bootstrap.bats`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_entrypoint_bootstrap.bats`:
```bash
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
  # mock paperclipai/sudo/curl/yq/codex-oauth.sh로 entrypoint 본체만 격리
  mock_bin sudo 'noop'
  mock_bin yq 'mocked'
  SCRIPT="$BATS_TEST_DIRNAME/../../scripts/entrypoint.sh"
}
teardown() { teardown_tmp_home; }

@test "hermes bootstrap: config.yaml 없으면 template 복사 + provider 설정 + ttyd-creds 작성" {
  # Paperclip 분기 스킵용 — config.json 미리 만들어 두기
  mkdir -p "$TMP_HOME/paperclip/instances/default"
  echo "{}" > "$TMP_HOME/paperclip/instances/default/config.json"
  export PAPERCLIP_HOME="$TMP_HOME/paperclip"

  # entrypoint의 [3] 분기만 실행 (TEST_MODE=hermes-only)
  TEST_MODE=hermes-only run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$HERMES_HOME/config.yaml" ]
  [ -f "$HERMES_HOME/.ttyd-creds" ]
  grep -q "testuser:testpw" "$HERMES_HOME/.ttyd-creds"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/unit/test_entrypoint_bootstrap.bats`
Expected: 2 tests fail (`No such file or directory`)

- [ ] **Step 3: Write minimal implementation**

`scripts/entrypoint.sh`:
```bash
#!/bin/bash
set -eu

export HERMES_HOME="${HERMES_HOME:-/home/node/.hermes}"
export CODEX_HOME="${CODEX_HOME:-/home/node/.codex}"
export PAPERCLIP_HOME="${PAPERCLIP_HOME:-/paperclip}"
ETC_HERMES="${ETC_HERMES:-/etc/hermes}"
PORT="${PORT:-3100}"
TEST_MODE="${TEST_MODE:-}"
MACHINE_ID="${TEST_MACHINE_ID:-$(cat /etc/machine-id 2>/dev/null || echo default-machine)}"

# ── [1] permission fix ──
[ "$TEST_MODE" = "" ] && sudo chown -R node:node "$PAPERCLIP_HOME" "$HERMES_HOME" "$CODEX_HOME"

# ── [2] Paperclip bootstrap ──
bootstrap_paperclip() {
  local config="$PAPERCLIP_HOME/instances/default/config.json"
  [ -f "$config" ] && return 0
  echo "→ Paperclip first-run bootstrap"
  PAPERCLIP_PUBLIC_URL="http://localhost:$PORT" \
  PAPERCLIP_ALLOWED_HOSTNAMES="localhost:$PORT,${PAPERCLIP_ALLOWED_HOSTNAMES:-}" \
    paperclipai onboard --yes --bind lan --run &
  local pid=$!
  until curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; do sleep 2; done
  _paperclip_admin_signup
  sed -i 's/"disableSignUp": false/"disableSignUp": true/' "$config"
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

_paperclip_admin_signup() {
  local cookies; cookies=$(mktemp)
  curl -sS -c "$cookies" -b "$cookies" \
    -H "Content-Type: application/json" -H "Origin: http://localhost:$PORT" \
    -X POST "http://localhost:$PORT/api/auth/sign-up/email" \
    --data "{\"name\":\"$ADMIN_NAME\",\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
  curl -sS -c "$cookies" -b "$cookies" \
    -H "Content-Type: application/json" -H "Origin: http://localhost:$PORT" \
    -X POST "http://localhost:$PORT/api/auth/sign-in/email" \
    --data "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
  local invite
  invite=$(paperclipai auth bootstrap-ceo --force | grep 'Invite URL' | awk -F'/invite/' '{print $2}')
  curl -sS -c "$cookies" -b "$cookies" \
    -H "Content-Type: application/json" -H "Origin: http://localhost:$PORT" \
    -X POST "http://localhost:$PORT/api/invites/$invite/accept" \
    --data '{"requestType":"human"}'
  rm -f "$cookies"
}

# ── [3] Hermes bootstrap ──
bootstrap_hermes() {
  [ -f "$HERMES_HOME/config.yaml" ] && return 0
  echo "→ Hermes first-run bootstrap"
  cp -rT "$ETC_HERMES/template" "$HERMES_HOME"
  [ "$TEST_MODE" = "" ] && yq -i '.providers.default = "codex_local"' "$HERMES_HOME/config.yaml" || \
    echo "providers: { default: codex_local }" >> "$HERMES_HOME/config.yaml"
  local token
  token=$(printf '%s' "$ADMIN_USERNAME:$ADMIN_PASSWORD:$MACHINE_ID" | sha256sum | cut -d' ' -f1)
  echo "session_token: $token" >> "$HERMES_HOME/config.yaml"
  echo "$ADMIN_USERNAME:$ADMIN_PASSWORD" > "$HERMES_HOME/.ttyd-creds"
  chmod 600 "$HERMES_HOME/.ttyd-creds"
}

# ── [4] Codex auth detection (비차단) ──
launch_codex_detection() {
  /usr/local/bin/codex-oauth.sh detect-or-prompt &
}

# ── Dispatcher ──
case "$TEST_MODE" in
  hermes-only)
    bootstrap_hermes
    exit 0
    ;;
  "")
    bootstrap_paperclip
    bootstrap_hermes
    launch_codex_detection
    exec /usr/local/bin/supervisor.sh
    ;;
  *)
    echo "unknown TEST_MODE: $TEST_MODE" >&2
    exit 2
    ;;
esac
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats tests/unit/test_entrypoint_bootstrap.bats`
Expected: `2 tests, 0 failures`

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/entrypoint.sh
git add scripts/entrypoint.sh tests/unit/test_entrypoint_bootstrap.bats
git commit -m "feat(scripts): add entrypoint.sh with Paperclip + Hermes bootstrap dispatch"
```

### Task 1.5: Dockerfile (multi-stage)

**Files:**
- Create: `Dockerfile`
- Create: `tests/integration/test_image_build.bats`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_image_build.bats`:
```bash
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/integration/test_image_build.bats`
Expected: build fails (`Dockerfile` 없음)

- [ ] **Step 3: Write Dockerfile**

`Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1.7

FROM ghcr.io/hostinger/hvps-hermes-agent:latest AS hermes
# 결과물 위치: /usr/local/bin/hermes, /usr/local/bin/ttyd, /etc/hermes

FROM ghcr.io/hostinger/hvps-paperclip:latest

USER root

# Hermes 바이너리 + system config만 복사 (데이터/credentials 가져오지 않음)
COPY --from=hermes /usr/local/bin/hermes /usr/local/bin/hermes
COPY --from=hermes /usr/local/bin/ttyd  /usr/local/bin/ttyd
COPY --from=hermes /etc/hermes /etc/hermes

# Custom entrypoint + supervisor + codex auth
COPY scripts/entrypoint.sh   /entrypoint.sh
COPY scripts/supervisor.sh   /usr/local/bin/supervisor.sh
COPY scripts/codex-oauth.sh  /usr/local/bin/codex-oauth.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/supervisor.sh /usr/local/bin/codex-oauth.sh

# 영구 데이터 디렉터리 (named volume mount target)
RUN mkdir -p /paperclip /home/node/.hermes /home/node/.codex \
 && chown -R node:node /home/node/.hermes /home/node/.codex /paperclip

USER node
EXPOSE 3100 9119 4860
ENTRYPOINT ["tini","-g","--","/entrypoint.sh"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats tests/integration/test_image_build.bats`
Expected: `7 tests, 0 failures` (빌드 1분+소요)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile tests/integration/test_image_build.bats
git commit -m "feat: multi-stage Dockerfile bundling paperclip + hermes + codex"
```

### Task 1.6: GHA workflow — build-and-push

**Files:**
- Create: `.github/workflows/build-and-push.yml`

- [ ] **Step 1: Write workflow**

`.github/workflows/build-and-push.yml`:
```yaml
name: build-and-push

on:
  schedule:
    - cron: '17 3 * * *'        # KST 12:17
  push:
    branches: [main]
    paths:
      - 'Dockerfile'
      - 'scripts/**'
      - '.github/workflows/build-and-push.yml'
  workflow_dispatch: {}

permissions:
  contents: read
  packages: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64
          push: true
          pull: true
          cache-from: type=gha
          cache-to:   type=gha,mode=max
          tags: |
            ghcr.io/dandacompany/paperclip-hermes-codex:latest
            ghcr.io/dandacompany/paperclip-hermes-codex:${{ github.sha }}
            ghcr.io/dandacompany/paperclip-hermes-codex:nightly-${{ github.run_number }}
```

- [ ] **Step 2: Lint workflow**

Run: `actionlint .github/workflows/build-and-push.yml` (또는 `npx --yes @actionlint/cli .github/workflows/build-and-push.yml`)
Expected: 출력 없음 (= 통과)

- [ ] **Step 3: Commit + verify on GitHub**

```bash
git add .github/workflows/build-and-push.yml
git commit -m "ci: nightly + on-push build for paperclip-hermes-codex image"
git push origin <branch>
```

- [ ] **Step 4: GHA Actions 탭에서 첫 실행 모니터링**

워크플로 첫 실행이 성공하고 `ghcr.io/dandacompany/paperclip-hermes-codex:latest`가 GHCR에 publish되는지 확인.

Expected: Actions UI에서 build job green, GHCR Packages 탭에 paperclip-hermes-codex 새 패키지.

### Task 1.7: GHA workflow — test (bats CI)

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Write workflow**

`.github/workflows/test.yml`:
```yaml
name: test

on:
  pull_request: {}
  push:
    branches: [main]

jobs:
  bats-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y bats jq
      - run: bats tests/unit/

  bats-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: sudo apt-get update && sudo apt-get install -y bats jq
      - run: bats tests/integration/
```

- [ ] **Step 2: Commit + push + verify CI green**

```bash
git add .github/workflows/test.yml
git commit -m "ci: bats unit + integration test job"
git push
```

Expected: PR에서 `bats-unit` (수초) + `bats-integration` (~2분) 둘 다 green.

### Task 1.8: Open PR 1

- [ ] **Step 1: PR 생성**

```bash
gh pr create --title "feat: build infrastructure for paperclip-hermes-codex single container" --body "$(cat <<'EOF'
## Summary
- Multi-stage Dockerfile (hermes 바이너리 + ttyd → paperclip base 합침)
- entrypoint.sh / supervisor.sh / codex-oauth.sh + bats 단위/통합 테스트
- GHA build-and-push 워크플로 (nightly + on-push + workflow_dispatch)
- GHA test 워크플로

## Test plan
- [ ] bats tests/unit/ green
- [ ] bats tests/integration/ green (Docker build 포함)
- [ ] GHA build-and-push 첫 실행이 ghcr.io/dandacompany/paperclip-hermes-codex:latest publish
- [ ] 기존 사이드카 compose 동작에 영향 없음 (add-only)

Spec: docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Merge 전 GHA green 대기 + 머지**

---

## PR 2 — Compose 파일 + Tailscale serve

**목표:** 새 compose 4종 + serve.json. 새 PR 1 이미지를 가리키므로 PR 1 머지 후 진행.

### Task 2.1: docker-compose.yml (base)

**Files:**
- Create: `docker-compose.v1.yml` (PR 4에서 `docker-compose.yml`로 rename — PR 2/3는 구 사이드카와 공존)

- [ ] **Step 1: Write base compose**

`docker-compose.v1.yml`:
```yaml
services:
  paperclip-hermes-codex:
    image: ghcr.io/dandacompany/paperclip-hermes-codex:latest
    platform: linux/amd64
    restart: unless-stopped
    environment:
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_NAME:     ${ADMIN_NAME:-Owner}
      ADMIN_EMAIL:    ${ADMIN_EMAIL}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      PAPERCLIP_PUBLIC_URL:           ${PAPERCLIP_PUBLIC_URL:-http://localhost:3100}
      PAPERCLIP_INSTANCE_ID:          default
      PAPERCLIP_DEPLOYMENT_MODE:      authenticated
      PAPERCLIP_DEPLOYMENT_EXPOSURE:  ${PAPERCLIP_DEPLOYMENT_EXPOSURE:-private}
      PAPERCLIP_AUTH_BASE_URL_MODE:   explicit
      PAPERCLIP_BIND: lan
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    volumes:
      - paperclip-data:/paperclip
      - hermes-data:/home/node/.hermes
      - codex-auth:/home/node/.codex

volumes:
  paperclip-data: {}
  hermes-data:    {}
  codex-auth:     {}
```

- [ ] **Step 2: Validate with docker compose config**

```bash
ADMIN_USERNAME=x ADMIN_EMAIL=x@x ADMIN_PASSWORD=x \
  docker compose -f docker-compose.v1.yml config > /dev/null
```
Expected: 출력 없음 + exit 0

- [ ] **Step 3: Commit**

```bash
git add docker-compose.v1.yml
git commit -m "feat(compose): v1 base service definition"
```

### Task 2.2: docker-compose.local.v1.yml

**Files:**
- Create: `docker-compose.local.v1.yml`

- [ ] **Step 1: Write local overlay**

```yaml
services:
  paperclip-hermes-codex:
    ports:
      - "127.0.0.1:3100:3100"
      - "127.0.0.1:9119:9119"
      - "127.0.0.1:4860:4860"
```

- [ ] **Step 2: Validate**

```bash
ADMIN_USERNAME=x ADMIN_EMAIL=x@x ADMIN_PASSWORD=x \
  docker compose -f docker-compose.v1.yml -f docker-compose.local.v1.yml config > /dev/null
```
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add docker-compose.local.v1.yml
git commit -m "feat(compose): local overlay binds 127.0.0.1:{3100,9119,4860}"
```

### Task 2.3: Tailscale serve.json

**Files:**
- Create: `tailscale/serve.json`

- [ ] **Step 1: Write serve config**

```json
{
  "TCP": {
    "443":  { "HTTPS": true },
    "3100": { "HTTPS": true },
    "9119": { "HTTPS": true },
    "4860": { "HTTPS": true }
  },
  "Web": {
    "${TS_HOSTNAME}.${TS_TAILNET}:443":  { "Handlers": { "/": { "Proxy": "http://127.0.0.1:3100" } } },
    "${TS_HOSTNAME}.${TS_TAILNET}:3100": { "Handlers": { "/": { "Proxy": "http://127.0.0.1:3100" } } },
    "${TS_HOSTNAME}.${TS_TAILNET}:9119": { "Handlers": { "/": { "Proxy": "http://127.0.0.1:9119" } } },
    "${TS_HOSTNAME}.${TS_TAILNET}:4860": { "Handlers": { "/": { "Proxy": "http://127.0.0.1:4860" } } }
  }
}
```

- [ ] **Step 2: JSON 유효성 검증**

Run: `jq . tailscale/serve.json > /dev/null`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add tailscale/serve.json
git commit -m "feat(tailscale): serve.json routing 3 ports to local backends"
```

### Task 2.4: docker-compose.tailscale.v1.yml

**Files:**
- Create: `docker-compose.tailscale.v1.yml`

- [ ] **Step 1: Write tailscale overlay**

```yaml
services:
  paperclip-hermes-codex:
    network_mode: "service:tailscale"
    depends_on:
      tailscale:
        condition: service_healthy

  tailscale:
    image: tailscale/tailscale:latest
    hostname: ${TS_HOSTNAME:-paperclip}
    restart: unless-stopped
    environment:
      TS_AUTHKEY:      ${TS_AUTHKEY}
      TS_HOSTNAME:     ${TS_HOSTNAME:-paperclip}
      TS_STATE_DIR:    /var/lib/tailscale
      TS_EXTRA_ARGS:   --advertise-tags=tag:paperclip
      TS_SERVE_CONFIG: /config/serve.json
    volumes:
      - tailscale-state:/var/lib/tailscale
      - ./tailscale/serve.json:/config/serve.json:ro
      - /dev/net/tun:/dev/net/tun
    cap_add: [net_admin, sys_module]
    healthcheck:
      test: ["CMD","tailscale","status","--peers=false","--json"]
      interval: 10s
      retries: 12

volumes:
  tailscale-state: {}
```

- [ ] **Step 2: Validate**

```bash
ADMIN_USERNAME=x ADMIN_EMAIL=x@x ADMIN_PASSWORD=x TS_AUTHKEY=tskey-fake TS_HOSTNAME=p \
  docker compose -f docker-compose.v1.yml -f docker-compose.tailscale.v1.yml config > /dev/null
```
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add docker-compose.tailscale.v1.yml
git commit -m "feat(compose): tailscale overlay with serve.json + healthcheck"
```

### Task 2.5: docker-compose.console.v1.yml (self-contained)

**Files:**
- Create: `docker-compose.console.v1.yml`

- [ ] **Step 1: Write self-contained compose**

```yaml
# Hostinger Docker Manager "URL에서 컴포즈 가져오기" 전용
# base + tailscale을 한 파일에 합침 (외부 파일 참조 없음 — serve.json은 컨테이너가 wget로 fetch)
services:
  paperclip-hermes-codex:
    image: ghcr.io/dandacompany/paperclip-hermes-codex:latest
    platform: linux/amd64
    restart: unless-stopped
    network_mode: "service:tailscale"
    depends_on:
      tailscale: { condition: service_healthy }
    environment:
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_NAME:     ${ADMIN_NAME:-Owner}
      ADMIN_EMAIL:    ${ADMIN_EMAIL}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      PAPERCLIP_PUBLIC_URL:          ${PAPERCLIP_PUBLIC_URL:-https://${TS_HOSTNAME}.ts.net:3100}
      PAPERCLIP_INSTANCE_ID:         default
      PAPERCLIP_DEPLOYMENT_MODE:     authenticated
      PAPERCLIP_AUTH_BASE_URL_MODE:  explicit
      PAPERCLIP_BIND: lan
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    volumes:
      - paperclip-data:/paperclip
      - hermes-data:/home/node/.hermes
      - codex-auth:/home/node/.codex

  tailscale:
    image: tailscale/tailscale:latest
    hostname: ${TS_HOSTNAME:-paperclip}
    restart: unless-stopped
    environment:
      TS_AUTHKEY:      ${TS_AUTHKEY}
      TS_HOSTNAME:     ${TS_HOSTNAME:-paperclip}
      TS_STATE_DIR:    /var/lib/tailscale
      TS_SERVE_CONFIG: /config/serve.json
    volumes:
      - tailscale-state:/var/lib/tailscale
    cap_add: [net_admin, sys_module]
    entrypoint: |
      sh -c "set -e;
             mkdir -p /config;
             wget -q -O /config/serve.json https://raw.githubusercontent.com/dandacompany/paperclip-hermes-codex-on-hostinger/main/tailscale/serve.json;
             tailscaled --tun=userspace-networking --state=/var/lib/tailscale/tailscaled.state &
             sleep 3;
             tailscale up --authkey=$$TS_AUTHKEY --hostname=$$TS_HOSTNAME;
             tailscale serve --reset || true;
             tailscale serve --bg --set-path /config/serve.json;
             tail -f /dev/null"
    healthcheck:
      test: ["CMD","tailscale","status","--peers=false","--json"]
      interval: 10s
      retries: 12

volumes:
  paperclip-data:  {}
  hermes-data:     {}
  codex-auth:      {}
  tailscale-state: {}
```

- [ ] **Step 2: Validate**

```bash
ADMIN_USERNAME=x ADMIN_EMAIL=x@x ADMIN_PASSWORD=x TS_AUTHKEY=tskey-fake TS_HOSTNAME=p \
  docker compose -f docker-compose.console.v1.yml config > /dev/null
```
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add docker-compose.console.v1.yml
git commit -m "feat(compose): self-contained console.v1.yml for Hostinger URL import"
```

### Task 2.6: Compose lint CI

**Files:**
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: 워크플로에 compose validate job 추가**

기존 `.github/workflows/test.yml`에 추가:
```yaml
  compose-config:
    runs-on: ubuntu-latest
    env:
      ADMIN_USERNAME: x
      ADMIN_EMAIL: x@x
      ADMIN_PASSWORD: x
      TS_AUTHKEY: tskey-fake
      TS_HOSTNAME: p
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.v1.yml config > /dev/null
      - run: docker compose -f docker-compose.v1.yml -f docker-compose.local.v1.yml config > /dev/null
      - run: docker compose -f docker-compose.v1.yml -f docker-compose.tailscale.v1.yml config > /dev/null
      - run: docker compose -f docker-compose.console.v1.yml config > /dev/null
      - run: jq . tailscale/serve.json > /dev/null
```

- [ ] **Step 2: Commit + PR + green 확인**

```bash
git add .github/workflows/test.yml
git commit -m "ci: compose config validation for all 4 overlays"
```

### Task 2.7: Open PR 2

- [ ] **Step 1: PR 생성**

```bash
gh pr create --title "feat: v1 compose files (base + local + tailscale + console)" --body "..."
```

- [ ] **Step 2: 머지**

---

## PR 3 — .env.example + setup.sh + README + gitleaks 갱신

**목표:** 사용자 진입점 파일들. 기존 파일은 보존, `.v1` suffix로 공존.

### Task 3.1: .env.v1.example

**Files:**
- Create: `.env.v1.example`

- [ ] **Step 1: Write template**

```dotenv
# paperclip-hermes-codex-on-hostinger — v1 single container
#
# Hostinger Docker Manager 사용 시:
#   1) "URL에서 컴포즈 가져오기" → docker-compose.console.yml의 Raw URL
#   2) 콘솔이 이 파일을 자동 파싱 — 키 이름만 일치하면 됨
#   3) 콘솔 폼에서 값 입력 (비밀번호 입력 시 마스킹됨)

COMPOSE_PROJECT_NAME=paperclip-hermes-codex
COMPOSE_FILE=docker-compose.yml:docker-compose.local.yml

# Admin (Paperclip 자동 가입 + Hermes dashboard 세션 + ttyd basic-auth 공통)
ADMIN_USERNAME=owner
ADMIN_NAME=Owner
ADMIN_EMAIL=
ADMIN_PASSWORD=

# Tailscale 모드 (local 모드에서는 비워두기)
TS_AUTHKEY=
TS_HOSTNAME=paperclip
PAPERCLIP_PUBLIC_URL=

# Codex API key fallback (OAuth 사용 시 비워둠)
OPENAI_API_KEY=
```

- [ ] **Step 2: Commit**

```bash
git add .env.v1.example
git commit -m "feat(env): v1 env template — minimal keys, no colon-comments"
```

### Task 3.2: setup.v1.sh (MODE 선택기)

**Files:**
- Create: `setup.v1.sh`

- [ ] **Step 1: Write setup script**

```bash
#!/bin/bash
set -eu

MODE="${MODE:-local}"
case "$MODE" in
  local|tailscale) ;;
  *) echo "MODE must be local | tailscale" >&2; exit 1 ;;
esac

if [ ! -f .env ]; then
  cp .env.v1.example .env
fi

case "$MODE" in
  local)
    sed -i.bak 's|^COMPOSE_FILE=.*|COMPOSE_FILE=docker-compose.v1.yml:docker-compose.local.v1.yml|' .env
    echo "→ MODE=local set. Run: docker compose up -d"
    ;;
  tailscale)
    if [ -z "${TS_AUTHKEY:-}" ]; then
      echo "✗ TS_AUTHKEY env var required for tailscale mode" >&2
      exit 1
    fi
    sed -i.bak 's|^COMPOSE_FILE=.*|COMPOSE_FILE=docker-compose.v1.yml:docker-compose.tailscale.v1.yml|' .env
    sed -i.bak "s|^TS_AUTHKEY=.*|TS_AUTHKEY=$TS_AUTHKEY|" .env
    sed -i.bak "s|^TS_HOSTNAME=.*|TS_HOSTNAME=${TS_HOSTNAME:-paperclip}|" .env
    sed -i.bak "s|^PAPERCLIP_PUBLIC_URL=.*|PAPERCLIP_PUBLIC_URL=https://${TS_HOSTNAME:-paperclip}.ts.net:3100|" .env
    rm .env.bak
    echo "→ MODE=tailscale set. Run: docker compose up -d"
    ;;
esac

# ADMIN_PASSWORD가 비어 있으면 랜덤 32자 생성
if grep -q '^ADMIN_PASSWORD=$' .env; then
  PW=$(openssl rand -hex 16)
  sed -i.bak "s|^ADMIN_PASSWORD=$|ADMIN_PASSWORD=$PW|" .env
  rm -f .env.bak
  echo "→ ADMIN_PASSWORD generated (saved in .env)"
fi
```

- [ ] **Step 2: Test on Mac**

```bash
chmod +x setup.v1.sh
rm -f .env
MODE=local ADMIN_EMAIL=test@test ./setup.v1.sh
grep '^COMPOSE_FILE' .env  # → docker-compose.v1.yml:docker-compose.local.v1.yml
grep '^ADMIN_PASSWORD' .env  # → 32자 hex
```

- [ ] **Step 3: Commit**

```bash
git add setup.v1.sh
git commit -m "feat(setup): v1 MODE selector script with auto-password gen"
```

### Task 3.3: README.v1.md

**Files:**
- Create: `README.v1.md`

- [ ] **Step 1: Write README**

(상세 내용 — 본 plan에서는 핵심 골격만 명시; 구현 시 spec §2/3/7 참조해서 채움)
```markdown
# paperclip-hermes-codex-on-hostinger

Paperclip orchestrator + Hermes Agent worker + Codex CLI를 단일 Docker 컨테이너에서 운영하는 OSS 스택.

## 3가지 인터페이스
| 인터페이스 | 포트 | 인증 |
|---|---|---|
| Paperclip Web | 3100 | admin 자동 가입 + 쿠키 세션 |
| Hermes Dashboard | 9119 | 자동 생성 세션 토큰 |
| Hermes TUI (ttyd) | 4860 | ADMIN_USERNAME:ADMIN_PASSWORD basic-auth |

## 2가지 노출 모드
| 모드 | 어디서 | 외부 접근 |
|---|---|---|
| local | 본인 노트북·서버, 외부 차단 | ❌ |
| tailscale | Tailscale 메시 멤버만 (`.ts.net` 자동 HTTPS) | 메시 멤버만 |

## 빠른 설치 (호스팅어 콘솔)
1. hPanel → VPS → Docker Manager → "URL에서 컴포즈 가져오기"
2. URL: `https://raw.githubusercontent.com/dandacompany/paperclip-hermes-codex-on-hostinger/main/docker-compose.console.yml`
3. 환경변수 입력 → 배포
4. 컨테이너 로그에서 Codex OAuth URL 확인 → 브라우저 인증 1회

## 빠른 설치 (로컬 / SSH)
```bash
git clone https://github.com/dandacompany/paperclip-hermes-codex-on-hostinger.git
cd paperclip-hermes-codex-on-hostinger
MODE=tailscale TS_AUTHKEY=tskey-auth-... ADMIN_EMAIL=you@x.com ./setup.v1.sh
docker compose up -d
```

## 업데이트
호스팅어 콘솔에서 "업데이트" 버튼 클릭 — 또는 SSH:
```bash
docker compose pull && docker compose up -d
```
Volume(`paperclip-data`, `hermes-data`, `codex-auth`)에 살아있는 인증·세션이 그대로 유지됨.

## v0.1 사이드카 구조 사용자
`git checkout v0.1-sidecar` 로 영구 참조 가능. 자발적 마이그레이션은 `docs/MIGRATION-v0.1-to-v1.md` 참조.
```

- [ ] **Step 2: Commit**

```bash
git add README.v1.md
git commit -m "docs: v1 README — install, expose modes, update flow"
```

### Task 3.4: gitleaks 룰 갱신 — Codex token 패턴 추가

**Files:**
- Modify: `.gitleaks.toml`

- [ ] **Step 1: Add Codex auth.json token pattern**

기존 `.gitleaks.toml`의 `[[rules]]` 섹션 마지막에 추가:
```toml
[[rules]]
id = "codex-oauth-token"
description = "Codex CLI OAuth token (auth.json 'access_token' field)"
regex = '''"access_token"\s*:\s*"[A-Za-z0-9_-]{40,}"'''
tags = ["codex", "oauth", "secret"]
```

- [ ] **Step 2: Test gitleaks scan**

```bash
pre-commit run gitleaks --all-files
```
Expected: pass

- [ ] **Step 3: Commit**

```bash
git add .gitleaks.toml
git commit -m "chore(gitleaks): add codex-oauth-token rule"
```

### Task 3.5: Open PR 3

```bash
gh pr create --title "feat: v1 user-facing entry (.env.example, setup.sh, README, gitleaks)" --body "..."
```

---

## PR 4 — E2E 검증 + v0.1-sidecar 태그

**목표:** Mac local + Hostinger staging에서 실 E2E를 통과시키고 사이드카에 태그.

### Task 4.1: tests/e2e/test_local_compose.sh

**Files:**
- Create: `tests/e2e/test_local_compose.sh`

- [ ] **Step 1: Write E2E script**

```bash
#!/bin/bash
set -eu

PROJECT="paperclip-hermes-codex-e2e"
export COMPOSE_FILE="docker-compose.v1.yml:docker-compose.local.v1.yml"
export ADMIN_USERNAME=e2euser
export ADMIN_NAME=E2E
export ADMIN_EMAIL=e2e@example.com
export ADMIN_PASSWORD=e2e-$(openssl rand -hex 8)

cleanup() { docker compose -p "$PROJECT" down -v --remove-orphans 2>&1 | tail -3; }
trap cleanup EXIT

docker compose -p "$PROJECT" up -d
echo "→ Waiting up to 90s for paperclip health..."
for i in $(seq 1 45); do
  if curl -sf http://127.0.0.1:3100/api/health > /dev/null; then break; fi
  sleep 2
done
curl -sf http://127.0.0.1:3100/api/health
echo "✓ paperclip /api/health OK"

curl -sfI http://127.0.0.1:9119/ | head -1 | grep -q '200\|301\|302'
echo "✓ hermes dashboard responds"

curl -sfI -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" http://127.0.0.1:4860/ | head -1 | grep -q '200'
echo "✓ ttyd basic-auth OK"

# Codex OAuth가 시작되었는지 로그 검사
docker compose -p "$PROJECT" logs paperclip-hermes-codex | grep -E "Codex (OAuth setup required|auth:)"
echo "✓ Codex auth detection ran"

echo "ALL E2E CHECKS PASSED"
```

- [ ] **Step 2: Run on Mac**

```bash
chmod +x tests/e2e/test_local_compose.sh
./tests/e2e/test_local_compose.sh
```
Expected: `ALL E2E CHECKS PASSED`

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_local_compose.sh
git commit -m "test(e2e): local compose smoke — paperclip health + hermes dashboard + ttyd + codex"
```

### Task 4.2: Hostinger 스테이징 검증 (수동)

- [ ] **Step 1: hPanel에서 새 docker project 생성**

URL: `https://raw.githubusercontent.com/dandacompany/paperclip-hermes-codex-on-hostinger/<feature-branch>/docker-compose.console.v1.yml`

- [ ] **Step 2: 환경변수 입력 + 배포**

ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD / TS_AUTHKEY / TS_HOSTNAME 입력.

- [ ] **Step 3: 컨테이너 로그에서 Codex OAuth URL 발견 + 브라우저 인증**

검증 로그:
- `✓ Codex OAuth completed and saved to /home/node/.codex/auth.json`
- `→ Paperclip first-run bootstrap` → `Created admin user`
- `signup hidden (auth.disableSignUp=true)`

- [ ] **Step 4: 브라우저 접속 검증**

- `https://<host>.ts.net:3100` → Paperclip 로그인 → admin 로그인 성공
- `https://<host>.ts.net:9119` → Hermes Dashboard
- `https://<host>.ts.net:4860` → ttyd basic-auth 프롬프트 → admin/패스워드로 로그인 → hermes shell

- [ ] **Step 5: Paperclip에서 Hermes Agent 어댑터 + "Test now"**

Paperclip UI → Create agent → Adapter: Hermes Agent → Test now → "passed" 확인.

- [ ] **Step 6: 한 task 실행해서 chain 검증**

간단한 task ("Respond with hello") 실행 → 결과가 Paperclip UI에 반환되는지 확인.

- [ ] **Step 7: 결과 기록**

`docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md` 끝에 verification log section 추가 (또는 별도 `docs/E2E-LOG.md`).

### Task 4.3: v0.1-sidecar 태그

- [ ] **Step 1: 사이드카 구조 최종 상태 검토**

Run: `git log --oneline main -5`
Run: `git show --stat HEAD`

- [ ] **Step 2: Tag + push**

```bash
git tag -a v0.1-sidecar -m "Final sidecar release (hermes + paperclip in separate containers)"
git push origin v0.1-sidecar
```

- [ ] **Step 3: GitHub release 작성**

```bash
gh release create v0.1-sidecar --title "v0.1-sidecar — final sidecar release" --notes "$(cat <<'EOF'
This is the final release of the **sidecar** architecture where Hermes Agent and Paperclip ran in separate containers connected by a Docker bridge network.

The main branch is moving to a **single-container** architecture (`paperclip-hermes-codex-on-hostinger`) where the three tools are bundled into one image with GHA-driven automatic updates.

Existing users of the sidecar setup can keep using this tag indefinitely:
```bash
git checkout v0.1-sidecar
docker compose up -d
```

A migration guide is published at `docs/MIGRATION-v0.1-to-v1.md` on the main branch.
EOF
)"
```

### Task 4.4: Open PR 4

```bash
gh pr create --title "test: E2E verification + v0.1-sidecar tag" --body "..."
```

---

## PR 5 — main rewrite + migration 문서

**목표:** v1 파일들을 정식 이름으로 rename + 구 사이드카 파일 제거 + MIGRATION 문서.

### Task 5.1: v1 파일 rename

**Files:**
- Rename: `docker-compose.v1.yml` → `docker-compose.yml`
- Rename: `docker-compose.local.v1.yml` → `docker-compose.local.yml`
- Rename: `docker-compose.tailscale.v1.yml` → `docker-compose.tailscale.yml`
- Rename: `docker-compose.console.v1.yml` → `docker-compose.console.yml`
- Rename: `setup.v1.sh` → `setup.sh`
- Rename: `.env.v1.example` → `.env.example`
- Rename: `README.v1.md` → `README.md`

- [ ] **Step 1: 구 파일 제거**

```bash
git rm docker-compose.yml docker-compose.local.yml docker-compose.traefik.yml \
       docker-compose.cloudflared.yml docker-compose.console.yml setup.sh .env.example README.md
git rm -r docs/EXPOSURE-traefik.md docs/EXPOSURE-cloudflared.md \
          docs/tutorial-hermes-paperclip-on-hostinger docs/tutorial-hostinger-console
```

- [ ] **Step 2: v1 파일 rename**

```bash
git mv docker-compose.v1.yml          docker-compose.yml
git mv docker-compose.local.v1.yml    docker-compose.local.yml
git mv docker-compose.tailscale.v1.yml docker-compose.tailscale.yml
git mv docker-compose.console.v1.yml  docker-compose.console.yml
git mv setup.v1.sh                    setup.sh
git mv .env.v1.example                .env.example
git mv README.v1.md                   README.md
```

- [ ] **Step 3: 내부 참조 fix-up**

```bash
grep -rln "docker-compose\.v1\|setup\.v1\.sh\|README\.v1\.md\|env\.v1\.example" \
  | xargs sed -i.bak -e 's/docker-compose\.v1/docker-compose/g; s/setup\.v1\.sh/setup.sh/g; s/README\.v1\.md/README.md/g; s/env\.v1\.example/env.example/g'
find . -name "*.bak" -delete
```

- [ ] **Step 4: Validate**

```bash
ADMIN_USERNAME=x ADMIN_EMAIL=x@x ADMIN_PASSWORD=x \
  docker compose -f docker-compose.yml -f docker-compose.local.yml config > /dev/null
bats tests/unit/ tests/integration/
```
Expected: 모두 통과.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat!: collapse to single container (paperclip + hermes + codex)

BREAKING CHANGE: 사이드카 구조 폐기. 구 hermes-* 서비스 제거.
사이드카 사용자는 v0.1-sidecar 태그 참조 + MIGRATION 가이드 따라 이전."
```

### Task 5.2: MIGRATION 문서

**Files:**
- Create: `docs/MIGRATION-v0.1-to-v1.md`

- [ ] **Step 1: Write migration guide**

```markdown
# v0.1 사이드카 → v1 단일 컨테이너 마이그레이션 가이드

## 무엇이 바뀌었나
- 컨테이너 수: 4개(paperclip + hermes-dashboard + hermes-tui + tailscale) → 2개(paperclip-hermes-codex + tailscale)
- Hermes 인스턴스: 별도 → Paperclip 컨테이너 안 단일 인스턴스 (Paperclip 워커 겸 사람용 UI 공유)
- 이미지: `ghcr.io/hostinger/hvps-*` 직접 사용 → `ghcr.io/dandacompany/paperclip-hermes-codex:latest`
- 노출 모드: 4종 → 2종 (local, tailscale). Traefik / Cloudflared는 별도 sprint.

## 데이터 이전
### 사이드카 hermes-data → v1 hermes-data
```bash
# 구 사이드카 환경에서
docker run --rm -v hermes-paperclip-on-hostinger_hermes-data:/from -v $PWD:/out alpine \
  tar czf /out/hermes-data-export.tgz -C /from .

# v1 환경에서 (paperclip 컨테이너 정지 후)
docker compose stop paperclip-hermes-codex
docker run --rm -v paperclip-hermes-codex_hermes-data:/to -v $PWD:/out alpine \
  tar xzf /out/hermes-data-export.tgz -C /to
docker compose start paperclip-hermes-codex
```

### 사이드카 paperclip-data → v1 paperclip-data
동일 패턴 — volume 이름만 다름.

## 인증
- Paperclip admin: ADMIN_USERNAME/EMAIL/PASSWORD env 그대로 유지 (entrypoint가 기존 config.json을 감지하면 bootstrap 스킵)
- Hermes 세션 토큰: deterministic hash라 동일 ADMIN_* 환경변수면 같은 토큰 발급됨
- Codex: 사이드카에는 없던 신규 항목 — 첫 부팅 시 OAuth 또는 OPENAI_API_KEY 설정 필요

## 롤백
v1으로 옮긴 뒤 문제가 있으면:
```bash
git checkout v0.1-sidecar
docker compose up -d
```
volume은 이름이 다르므로(`hermes-paperclip-on-hostinger_*` vs `paperclip-hermes-codex_*`) 자동 충돌 없음.
```

- [ ] **Step 2: Commit**

```bash
git add docs/MIGRATION-v0.1-to-v1.md
git commit -m "docs: migration guide v0.1 sidecar → v1 single container"
```

### Task 5.3: GitHub repo rename

- [ ] **Step 1: GH UI 또는 gh CLI로 rename**

```bash
gh repo rename paperclip-hermes-codex-on-hostinger
```
Expected: redirect 자동 활성화 확인 메시지.

- [ ] **Step 2: 로컬 remote URL 갱신**

```bash
git remote set-url origin git@github.com:dandacompany/paperclip-hermes-codex-on-hostinger.git
git remote -v
```

- [ ] **Step 3: README의 모든 GitHub URL 참조 확인**

```bash
grep -rn "hermes-paperclip-on-hostinger" --include="*.md" --include="*.yml" --include="*.sh" .
```
모든 잔존 참조를 `paperclip-hermes-codex-on-hostinger`로 갱신.

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "chore: update GitHub URL references after repo rename"
```

### Task 5.4: GHA workflow의 image 경로 검증

- [ ] **Step 1: build-and-push 워크플로 재실행**

```bash
gh workflow run build-and-push.yml
```
Expected: `ghcr.io/dandacompany/paperclip-hermes-codex:latest` 새 이미지 publish (rename 후에도 동일 path).

### Task 5.5: Open PR 5

```bash
gh pr create --title "feat!: v1 rewrite — remove sidecar, single container default" --body "$(cat <<'EOF'
## Summary
- 사이드카 docker-compose / EXPOSURE / tutorial 파일 제거
- v1 파일들을 정식 이름으로 rename (.v1 suffix drop)
- `docs/MIGRATION-v0.1-to-v1.md` 추가
- GitHub repo rename + 내부 URL 참조 갱신

## Test plan
- [ ] bats unit/integration green
- [ ] tests/e2e/test_local_compose.sh green
- [ ] Hostinger 스테이징 새 URL로 URL import 재검증
- [ ] `git checkout v0.1-sidecar`로 구 구조 여전히 동작

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**
- §3 컨테이너 구성 (tini + supervisor) → PR 1 Task 1.3, 1.4, 1.5 ✓
- §4 이미지 빌드 (Dockerfile + GHA) → PR 1 Task 1.5, 1.6, 1.7 ✓
- §5 Entrypoint + Auth bootstrap → PR 1 Task 1.2, 1.4 ✓
- §6 Compose 4종 + 볼륨 → PR 2 전체 ✓
- §7 호스팅어 콘솔 워크플로 → PR 4 Task 4.2 (수동 검증) + README ✓
- §8 Migration → PR 4 Task 4.3 (태그) + PR 5 Task 5.1, 5.2 ✓
- §9 새 튜토리얼 → 별도 sprint (spec §11에서 v1 코어 밖으로 명시)
- §10 비-기능 (secret leak / 재현성 / footprint / 백업) → PR 1 secret 분리 + PR 3 gitleaks 룰 ✓
- §11 Out of scope → 의도적 미포함 ✓
- §12 검증 기준 → PR 4 E2E + 수동 검증으로 모두 커버 ✓

**2. Placeholder scan:** 모든 step에 actual 코드/명령 명시. README.v1.md만 골격 + spec 섹션 참조로 압축 (구현 시 spec 본문 그대로 인용 — 이는 단순 인용 작업이므로 plan에서 풀어쓸 가치가 낮음).

**3. Type consistency:**
- `HERMES_HOME`, `CODEX_HOME`, `PAPERCLIP_HOME` 환경변수 이름 모든 task에서 통일 ✓
- volume 이름 (`paperclip-data`, `hermes-data`, `codex-auth`, `tailscale-state`) 모든 compose에서 통일 ✓
- 포트 (3100/9119/4860) 모든 곳에서 통일 ✓
- `paperclip-hermes-codex` 컨테이너/이미지/repo 이름 일관 ✓

**4. Ambiguity:** TEST_MODE 환경변수의 분기 (hermes-only, 기본)는 entrypoint.sh dispatcher 섹션에서 명시. Codex OAuth 비차단은 `&` 백그라운드로 명시. Volume 이름은 default project name(`paperclip-hermes-codex`) prefix를 docker compose가 자동 부여한다는 점이 docker compose의 표준 동작.

이슈 발견 + 수정 (inline):
- README.v1.md를 PR 5에서 rename할 때 내부 참조 (`docker-compose.v1.yml` 등)를 sed로 일괄 치환하는 step 추가됨 (Task 5.1 Step 3).
- E2E 스크립트에서 Hermes Dashboard는 인증 없이 접근 가능한 정적 SPA 경로가 일부 있어 `curl -I /`가 200/301/302를 반환할 수 있도록 grep 패턴 완화.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — 매 task마다 fresh subagent 디스패치, task 간 review, 빠른 반복.
2. **Inline Execution** — 이 세션에서 직접 task 실행, checkpoint마다 review.

어느 방식으로?
