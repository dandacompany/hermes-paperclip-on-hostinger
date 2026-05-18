# Hostinger 원클릭 Paperclip + Hermes + Codex 통합 가이드

호스팅어의 원클릭 Paperclip 컨테이너 위에 Hermes Agent와 Codex CLI를 수동으로 얹어 멀티 에이전트 오케스트레이션을 운영하는 전체 절차. Tailscale로 보안 접근. 발견된 8개 함정 모두 해결책 포함.

마지막 검증: 2026-05-18 (Paperclip onboarding flow 기준)

---

## 목차

1. [구조 개요](#1-구조-개요)
2. [전제 조건](#2-전제-조건)
3. [STEP 01 — Hostinger 원클릭 Paperclip 설치](#step-01)
4. [STEP 02 — Tailscale 설치 + 인증](#step-02)
5. [STEP 03 — Tailscale serve + PAPERCLIP_PUBLIC_URL](#step-03)
6. [STEP 04 — Hermes·ttyd binary 추출](#step-04)
7. [STEP 05 — docker-compose 확장 + init 스크립트](#step-05)
8. [STEP 06 — 컨테이너 재시작 + 검증](#step-06)
9. [STEP 07 — Hermes OAuth 인증 (수동, 1회)](#step-07)
10. [STEP 08 — Hermes 기본 모델/프로바이더 설정](#step-08)
11. [STEP 09 — Paperclip Company + CEO 에이전트 생성](#step-09)
12. [STEP 10 — Persona(AGENTS.md) 작성](#step-10)
13. [STEP 11 — 가벼운 태스크로 체인 검증](#step-11)
14. [STEP 12 — Hermes Dashboard·ttyd 노출 (선택)](#step-12)
15. [Troubleshooting](#troubleshooting)
16. [Codex CLI 위임 프롬프트 (설치 자동화)](#codex-cli-위임-프롬프트)
17. [Paperclip CEO 운영 프롬프트](#paperclip-ceo-운영-프롬프트)
18. [Hostinger Update 버튼이 일어나면](#hostinger-update-버튼이-일어나면)

---

## 1. 구조 개요

```
   Internet
      │
      └─── Tailscale 메시 (외부에 직접 노출 0)
              │
              ▼
   ┌─ Hostinger VPS ──────────────────────────────────┐
   │  Tailscale daemon (host-level)                   │
   │      ↓ serves                                    │
   │  https://<host>.<tailnet>.ts.net  → :54748       │
   │                                       ↓          │
   │  Docker network                                  │
   │   ┌─ paperclip-kckc-paperclip-1 ──────────────┐  │
   │   │ image: ghcr.io/hostinger/hvps-paperclip   │  │
   │   │ entrypoint: /paperclip-tools/init.sh ──▶  │  │
   │   │   (1) apt install python3 + tini          │  │
   │   │   (2) symlink hermes → /usr/local/bin     │  │
   │   │   (3) sed patch hermes-paperclip-adapter  │  │
   │   │   (4) exec /entrypoint.sh (paperclip)     │  │
   │   │                                            │  │
   │   │ paperclipai server   :3100                 │  │
   │   │ hermes(spawned)  ← Hermes-paperclip-adapter│  │
   │   │   └─▶ ChatGPT Codex backend (OAuth)        │  │
   │   │                                            │  │
   │   │ Mounts:                                    │  │
   │   │  ./data            → /paperclip            │  │
   │   │  ./data/tools      → /paperclip-tools (ro) │  │
   │   │  ./data/tools/opt-hermes → /opt/hermes (ro)│  │
   │   │  ./data/tools/ttyd → /usr/local/bin/ttyd   │  │
   │   └────────────────────────────────────────────┘  │
   │                                                   │
   │  Codex CLI : 이 이미지에 이미 번들 (v0.130)         │
   └───────────────────────────────────────────────────┘
```

**왜 이 구조**

- Hostinger 원클릭 paperclip은 단독 컨테이너 (paperclipai만). 그 자체로는 Hermes를 못 spawn함.
- `init.sh`가 매 부팅마다 root 권한으로 빠진 의존성을 자동 보충하므로 호스팅어 Update 버튼·재시작 후에도 영구.
- Hermes와 ttyd는 hermes-agent 공식 이미지에서 추출해 host의 `./data/tools/`에 bind mount — 재빌드 없이 영구.
- Tailscale serve가 paperclip의 host 포트(`54748`)를 메시 전용 HTTPS로 노출. Traefik public exposure를 사용하지 않음.

---

## 2. 전제 조건

| 항목 | 비고 |
|---|---|
| Hostinger VPS (KVM 2+ 권장, RAM 2GB 이상) | Paperclip + Hermes Agent 합쳐 ~1.5GB |
| Hostinger hPanel API token | `~/.claude/auth/hostinger.env`의 `HOSTINGER_API_TOKEN` |
| Tailscale 계정 + reusable auth key | `https://login.tailscale.com/admin/settings/keys` |
| ChatGPT Plus/Pro 또는 Codex API 키 | Hermes의 openai-codex provider 인증 |
| 로컬에서 VPS SSH 별칭 | `~/.ssh/config`에 호스트 alias |

---

## STEP 01

### Hostinger 원클릭 Paperclip 설치

**hPanel UI 절차** (API 미노출):

1. hPanel → VPS → 대상 VPS 선택 → **OS & Panel → Operating System → Change OS**
2. **Application templates** 카테고리 → **Paperclip** 선택 → Install
3. 설치 마법사 입력:
   - Admin name: `Dante`
   - Email: `you@example.com`
   - Password: (강한 32자)
   - API key: 비워둠 (이후 Hermes provider OAuth 사용)
4. 설치 완료 후 hPanel → **Docker Manager**에 `paperclip-<random>` 프로젝트가 자동 등록됨

**설치 결과 검증**:

```bash
# VPS에 SSH
ssh root@<vps-ip>

# 컨테이너 + 프로젝트 확인
docker ps --format "{{.Names}}: {{.State}}" | grep paperclip
ls /docker/paperclip-*/
cat /docker/paperclip-*/.env | grep -E "ADMIN|TRAEFIK"
```

> Hostinger가 생성하는 컨테이너 이름은 `paperclip-<random>-paperclip-1` 형태. 이하 가이드에서 `paperclip-kckc-paperclip-1`로 표기 — 자신의 환경에서는 실제 이름으로 치환.

기본 노출은 Traefik HTTPS + Let's Encrypt:
```
http://paperclip-<random>.<vps-hostname>.hstgr.cloud
```
**이 공개 노출은 Tailscale로 대체 예정 — STEP 03에서 변경**.

---

## STEP 02

### Tailscale 설치 + 인증 (host-level)

```bash
ssh root@<vps-ip>
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled

# Tailscale admin에서 reusable auth key 발급 후
tailscale up --authkey=tskey-auth-... --hostname=paperclip-hostinger --ssh

tailscale status --peers=false --json | jq '.Self.DNSName'
```

기대 출력:
```
"paperclip-hostinger.tail7b1307.ts.net."
```

이 FQDN을 이후 단계에서 사용.

---

## STEP 03

### Tailscale serve + PAPERCLIP_PUBLIC_URL

**3-1. Tailscale에서 paperclip 노출**

paperclip 컨테이너의 host port를 확인:

```bash
docker port paperclip-kckc-paperclip-1
# 3100/tcp -> 0.0.0.0:54748
```

`54748` 같은 random host port를 Tailscale 443으로 매핑:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:54748
tailscale serve status
```

기대 출력:
```
https://paperclip-hostinger.tail7b1307.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:54748
```

**3-2. PAPERCLIP_PUBLIC_URL 갱신**

Hostinger 기본 compose는 `PAPERCLIP_PUBLIC_URL`을 Traefik FQDN으로 hardcode. `.env`로 override할 수 있게 compose를 한 번 수정:

```bash
cd /docker/paperclip-<random>/

# 1) compose가 .env 우선하도록 변경
sed -i.bak \
  -e 's|PAPERCLIP_PUBLIC_URL: http://${COMPOSE_PROJECT_NAME}.${TRAEFIK_HOST}|PAPERCLIP_PUBLIC_URL: ${PAPERCLIP_PUBLIC_URL:-http://${COMPOSE_PROJECT_NAME}.${TRAEFIK_HOST}}|' \
  -e 's|PAPERCLIP_ALLOWED_HOSTNAMES: ${TRAEFIK_HOST},${VPS_IP}:${PUBLIC_PORT}|PAPERCLIP_ALLOWED_HOSTNAMES: ${PAPERCLIP_ALLOWED_HOSTNAMES:-${TRAEFIK_HOST},${VPS_IP}:${PUBLIC_PORT}}|' \
  docker-compose.yml
rm -f docker-compose.yml.bak

# 2) .env에 Tailscale FQDN 추가
cat >> .env <<EOF
PAPERCLIP_PUBLIC_URL=https://paperclip-hostinger.tail7b1307.ts.net
PAPERCLIP_ALLOWED_HOSTNAMES=paperclip-hostinger.tail7b1307.ts.net,srv1431426.hstgr.cloud,156.67.219.3:54748
EOF
```

> `srv1431426`·IP 부분은 자기 VPS 값으로 치환.

---

## STEP 04

### Hermes·ttyd binary 추출 (1회)

```bash
mkdir -p /docker/paperclip-<random>/data/tools

docker create --name tmp-hermes ghcr.io/hostinger/hvps-hermes-agent:latest
docker cp tmp-hermes:/opt/hermes /docker/paperclip-<random>/data/tools/opt-hermes
docker cp tmp-hermes:/usr/bin/ttyd /docker/paperclip-<random>/data/tools/ttyd
docker rm tmp-hermes
```

> `/docker/.../data/tools/opt-hermes`가 약 1.9GB (Python venv 포함). bind mount로 컨테이너 안에서 read-only 사용.

---

## STEP 05

### docker-compose 확장 + init 스크립트

**5-1. init.sh 작성** (호스트의 영구 파일)

```bash
cat > /docker/paperclip-<random>/data/tools/init.sh <<'BASH'
#!/bin/bash
# Idempotent post-start init for Hostinger one-click paperclip + hermes stack.
# Runs every container start. node user has NOPASSWD sudo.

set -e

# 1) Install python3 + tini if absent (Debian 13 base lacks them)
if ! command -v python3 >/dev/null 2>&1 || ! command -v tini >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3 tini
fi

# 2) Symlink hermes binary to default PATH so plain `docker exec ... hermes ...` works
sudo ln -sf /opt/hermes/.venv/bin/hermes /usr/local/bin/hermes

# 3) Apply hermes-paperclip-adapter PR #123 patch (drop DEFAULT_MODEL fallback)
# https://github.com/NousResearch/hermes-paperclip-adapter/pull/123
ADAPTER_JS=/usr/local/lib/node_modules/paperclipai/node_modules/hermes-paperclip-adapter/dist/server/execute.js
if [ -f "$ADAPTER_JS" ] && grep -q "cfgString(config.model) || DEFAULT_MODEL" "$ADAPTER_JS" 2>/dev/null; then
  sudo sed -i "s#cfgString(config.model) || DEFAULT_MODEL#cfgString(config.model)#g" "$ADAPTER_JS"
fi

# 4) Hand off to original paperclip entrypoint
exec bash -c /entrypoint.sh
BASH
chmod +x /docker/paperclip-<random>/data/tools/init.sh
```

**5-2. docker-compose.yml에 mount + entrypoint 주입**

`cd /docker/paperclip-<random>/`에서 `docker-compose.yml`을 열어 `paperclip` 서비스의 `volumes` 직전에 entrypoint 라인 + 추가 마운트 삽입:

```yaml
    entrypoint: ["bash", "/paperclip-tools/init.sh"]
    volumes:
      - ./data:/paperclip
      - ./data/tools:/paperclip-tools:ro
      - ./data/tools/opt-hermes:/opt/hermes:ro
      - ./data/tools/ttyd:/usr/local/bin/ttyd:ro
```

---

## STEP 06

### 컨테이너 재시작 + 검증

```bash
cd /docker/paperclip-<random>/
docker compose up -d --force-recreate

# 약 30초 대기 후 검증
sleep 30
docker exec paperclip-<random>-paperclip-1 sh -c '
  echo --- python3, tini, hermes, ttyd ---
  command -v python3 tini hermes ttyd
  hermes --version
  echo --- adapter patch ---
  grep -c "cfgString(config.model) || DEFAULT_MODEL" \
    /usr/local/lib/node_modules/paperclipai/node_modules/hermes-paperclip-adapter/dist/server/execute.js
  echo --- paperclip health ---
  curl -sf http://127.0.0.1:3100/api/health
  echo --- auth origin ---
'
docker logs --tail 20 paperclip-<random>-paperclip-1 2>&1 | grep -i "authPublicBaseUrl"
```

기대:
- python3, tini, hermes, ttyd 모두 path resolve
- adapter remaining 0
- paperclip `/api/health` → `{"status":"ok","bootstrapStatus":"ready"}`
- `authPublicBaseUrl` → `https://<host>.<tailnet>.ts.net`

---

## STEP 07

### Hermes OAuth 인증 (수동, 1회)

ChatGPT 계정 OAuth 토큰을 Hermes의 `openai-codex` provider에 등록.

VPS host shell에서:

```bash
docker exec -it --user node paperclip-<random>-paperclip-1 \
  hermes auth add openai-codex --type oauth --no-browser
```

출력 예:
```
1. Open this link in your browser and sign in to your account
   https://auth.openai.com/codex/device
2. Enter this one-time code (expires in 15 minutes)
   6SYR-QWB3Z
```

브라우저로 URL 열고 ChatGPT 로그인 → 코드 입력 → 컨테이너 stdout에 `Logged in. Saved to /home/node/.hermes/auth.json` 확인.

검증:
```bash
docker exec --user node paperclip-<random>-paperclip-1 hermes auth status openai-codex
# → openai-codex: logged in
```

---

## STEP 08

### Hermes 기본 모델·프로바이더 설정

OAuth만으로는 부족. Hermes config에 default model을 명시해야 paperclip의 detect-model이 정상 작동.

```bash
docker exec --user node paperclip-<random>-paperclip-1 bash -c '
  hermes config set model.provider openai-codex
  hermes config set model.default gpt-5.5
  hermes config set model.base_url https://chatgpt.com/backend-api/codex
  echo --- verify ---
  hermes status | grep -E "Model|Provider"
'
```

기대:
```
Model:        gpt-5.5
Provider:     OpenAI Codex
```

---

## STEP 09

### Paperclip Company + CEO 에이전트 생성

Paperclip은 vanilla 설치에서 자동 company를 만들지 않음. 첫 사용 시 만들어야.

**브라우저 path**: `https://<host>.<tailnet>.ts.net/` 접속 → "Create company" 입력 → CEO agent 추가 시 Hermes Agent 어댑터 선택.

**또는 API path** (스크립트화):

```bash
# 9-1. paperclip login → cookie
ADMIN_PW=$(grep ADMIN_PASSWORD /docker/paperclip-<random>/.env | cut -d= -f2)

docker exec paperclip-<random>-paperclip-1 sh -c "
curl -sS -c /tmp/cookies.txt -b /tmp/cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://<host>.<tailnet>.ts.net' \
  -X POST http://localhost:3100/api/auth/sign-in/email \
  --data '{\"email\":\"you@example.com\",\"password\":\"$ADMIN_PW\"}'
"

# 9-2. company create
CID=$(docker exec paperclip-<random>-paperclip-1 sh -c '
  curl -sS -b /tmp/cookies.txt -H "Content-Type: application/json" -H "Origin: https://<host>.<tailnet>.ts.net" \
    -X POST http://localhost:3100/api/companies \
    --data "{\"name\":\"DanteLabs\"}"
' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "company id: $CID"

# 9-3. CEO agent
docker exec paperclip-<random>-paperclip-1 sh -c "
curl -sS -b /tmp/cookies.txt -H 'Content-Type: application/json' -H 'Origin: https://<host>.<tailnet>.ts.net' \
  -X POST http://localhost:3100/api/companies/$CID/agents \
  --data '{
    \"name\":\"CEO\",
    \"role\":\"ceo\",
    \"title\":\"Chief Executive Officer\",
    \"adapterType\":\"hermes_local\",
    \"adapterConfig\":{\"timeoutSec\":900,\"effort\":\"medium\",\"persistSession\":true},
    \"capabilities\":\"전사 전략 결정, 다중 에이전트 오케스트레이션\"
  }'
"
```

> `model`·`provider`는 **명시하지 않음**. STEP 05의 init.sh가 적용한 adapter patch 덕분에 paperclip이 Hermes config의 default(gpt-5.5/openai-codex)를 그대로 사용.

`adapterConfig` 권장값:
- `timeoutSec: 900` — gpt-5.5의 thinking phase가 길어 300초로는 부족
- `effort: "medium"` — reasoning 깊이 적정

---

## STEP 10

### Persona(AGENTS.md) 작성

CEO agent의 system prompt를 명시:

```bash
AGENT_ID=<step9에서 받은 CEO id>

# 호스트에 persona 작성
cat > /tmp/persona.md <<'PERSONA'
# 정체성

당신은 Dante Labs의 CEO입니다. AI·데이터 비즈니스 의사결정과 다중 Hermes 에이전트 조직 운영을 책임집니다. 기본 응답 언어는 한국어이며, 글로벌 컨텍스트(영문 자료·표기)는 자연스럽게 병기합니다.

# 책임

1. **전략 결정** — 회사 단기·장기 목표와 진행 중인 프로젝트의 우선순위 결정.
2. **에이전트 오케스트레이션** — 새 이슈가 들어오면 적절한 전문가 에이전트를 hire하거나 기존 에이전트에 위임.
3. **산출물 리뷰** — 각 에이전트의 결과 검토 + 후속 태스크 분배.
4. **보고·요약** — 결정 사유 + 다음 단계 권장 + 리소스 영향(시간·비용·리스크) 함께 명시.

# 운영 원칙

- "왜"와 "다음 행동"을 항상 함께.
- 출처·근거 표기. 추측은 "추측"으로 명시.
- Trade-off(빠름 vs 정확, 비용 vs 품질)를 결정 사유에 포함.
- 보안·컴플라이언스 영향 있는 결정은 별도 코멘트로 강조.
- 본인은 의사결정·위임·리뷰만. 코드/분석은 전문가 에이전트에게 위임.

# 응답 톤

- 간결, 단호, 사실 기반.
- 모르는 영역은 누구에게 위임할지 명시.
PERSONA

# 컨테이너로 복사 + PUT
docker cp /tmp/persona.md paperclip-<random>-paperclip-1:/tmp/persona.md
docker exec paperclip-<random>-paperclip-1 bash -c '
  python3 -c "import json,sys; print(json.dumps({\"path\":\"AGENTS.md\",\"content\":open(\"/tmp/persona.md\").read()}))" > /tmp/p.json
  curl -sS -b /tmp/cookies.txt -X PUT \
    -H "Content-Type: application/json" -H "Origin: https://<host>.<tailnet>.ts.net" \
    --data @/tmp/p.json \
    http://localhost:3100/api/agents/'"$AGENT_ID"'/instructions-bundle/file
'
```

Paperclip UI에서 agent → "Instructions" 섹션에서 markdown 직접 편집도 가능.

---

## STEP 11

### 가벼운 태스크로 체인 검증

```bash
CID=<step9>
AGENT_ID=<step9>

docker exec paperclip-<random>-paperclip-1 sh -c "
curl -sS -b /tmp/cookies.txt -X POST \
  -H 'Content-Type: application/json' -H 'Origin: https://<host>.<tailnet>.ts.net' \
  --data '{
    \"title\":\"GDP 약자 확인\",
    \"body\":\"GDP의 영문 풀네임을 한 문장으로 답하세요.\",
    \"status\":\"todo\",
    \"assigneeAgentId\":\"$AGENT_ID\"
  }' \
  http://localhost:3100/api/companies/$CID/issues
"
```

Paperclip UI에서 새 issue가 약 1.5분 후 `done` 상태로 전환되고 코멘트에 답이 달려야 정상.

CLI 로그 확인:
```bash
ISS=<issue id>
docker exec paperclip-<random>-paperclip-1 bash -c "
  RID=\$(curl -s -b /tmp/cookies.txt http://localhost:3100/api/issues/$ISS/runs \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d if isinstance(d,list) else d[\"runs\"])[0][\"runId\"])')
  curl -s -b /tmp/cookies.txt http://localhost:3100/api/heartbeat-runs/\$RID/log \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"content\"][:2000])'
"
```

기대 로그 라인:
```
[hermes] Starting Hermes Agent (model=undefined, provider=auto [auto], timeout=900s)
...
[hermes] Exit code: 0, timed out: false
```

---

## STEP 12

### Hermes Dashboard·ttyd 노출 (선택)

이 단계 없이도 Paperclip UI는 동작. Hermes Dashboard와 brower-terminal(ttyd)을 추가로 쓰고 싶을 때만.

**12-1. paperclip 컨테이너 안 background spawn**

```bash
docker exec -d --user node paperclip-<random>-paperclip-1 bash -c '
  hermes dashboard --port 9119 --host 0.0.0.0 --insecure --no-open --skip-build
'

ADMIN_USERNAME=dante
ADMIN_PASSWORD=$(grep ADMIN_PASSWORD /docker/paperclip-<random>/.env | cut -d= -f2)
docker exec -d --user node paperclip-<random>-paperclip-1 bash -c "
  ttyd -p 4860 -W -c \"$ADMIN_USERNAME:$ADMIN_PASSWORD\" hermes
"
```

**12-2. compose에 추가 포트 expose** (영구화 — 컨테이너 재시작 시 9119/4860도 host로 노출)

```yaml
    ports:
      - "${PUBLIC_PORT}:3100"
      - "9119:9119"
      - "4860:4860"
```

**12-3. Tailscale serve로 추가 매핑**

```bash
tailscale serve --bg --https=9119 http://127.0.0.1:9119
tailscale serve --bg --https=4860 http://127.0.0.1:4860
tailscale serve status
```

→ `https://<host>.<tailnet>.ts.net:9119` (Dashboard), `:4860` (ttyd basic-auth)

---

## Troubleshooting

8개 함정 — 실제 시뮬레이션에서 마주친 순서대로.

### T1. Hostinger 콘솔 Terminal 버튼이 "No such container"

원인: hPanel의 컨테이너 카드 Terminal 버튼은 페이지 로드 시점의 컨테이너 ID를 캐시. `docker compose up -d --force-recreate` 후 ID 바뀌면 stale link.

**해결**: 콘솔 페이지 새로고침 → 새 ID로 Terminal 다시. 또는 SSH로 `docker exec -it --user node <name> bash`.

### T2. `hermes: command not found` in container terminal

원인: hermes는 `/opt/hermes/.venv/bin/hermes`인데 PATH 미노출.

**해결**: STEP 05 init.sh의 `ln -sf` 라인 — `/usr/local/bin/hermes` 심볼릭. 적용 후엔 어디서나 `hermes`.

### T3. `hermes auth status` → logged out인데 token은 있음

원인: 컨테이너 default HOME이 `/paperclip`인데 token은 `/home/node/.hermes/auth.json`.

**해결**: 항상 `docker exec --user node ...`로 invoke. node user의 /etc/passwd home인 `/home/node`가 자동 적용. `--user node`만 빠뜨리지 말 것.

### T4. apt-get install: Permission denied

원인: image의 ENTRYPOINT는 node user로 실행. node가 `/var/lib/apt`에 쓰기 불가.

**해결**: image가 node에 NOPASSWD sudo 부여 — init.sh에서 `sudo apt-get install ...`.

### T5. paperclip container restart loop: `/entrypoint: No such file or directory`

원인: image entrypoint는 `bash -c "/entrypoint.sh"` (`.sh` 확장자 필수). custom wrapper에서 `/entrypoint`로 호출하면 ENOENT.

**해결**: init.sh 마지막 라인을 `exec bash -c /entrypoint.sh`로.

### T6. PAPERCLIP_PUBLIC_URL이 .env update해도 그대로

원인: `docker-compose.yml`의 environment 섹션이 hard-coded `http://${COMPOSE_PROJECT_NAME}.${TRAEFIK_HOST}`로 .env override.

**해결**: STEP 03의 sed 패치 — `${PAPERCLIP_PUBLIC_URL:-...}` 형태로 .env override 가능하게.

### T7. Hermes adapter spawns `model=anthropic/claude-sonnet-4` even though hermes config is openai-codex

원인: `hermes-paperclip-adapter` v0.2.1의 `DEFAULT_MODEL` fallback. agent.adapterConfig.model이 비면 anthropic으로 fallback.

**해결**: STEP 05 init.sh의 sed가 PR #123(`Use Hermes profile defaults when model is unset`)을 mirror. agent.adapterConfig.model 비워두면 hermes config의 default 사용.

### T8. Task: `Hermes isn't configured yet — no API keys or providers found`

원인: OAuth만 했고 `hermes config set model.provider/model.default/model.base_url`을 안 한 상태.

**해결**: STEP 08의 3줄 config set. `hermes status`에서 Model/Provider가 정확히 나오는지 확인.

---

## Codex CLI 위임 프롬프트

설치·트러블슈팅 자동화 위임. Codex CLI는 paperclip image에 이미 번들(v0.130).

VPS host shell에서:

```
docker exec -it --user node paperclip-<random>-paperclip-1 codex
```

또는 non-interactive `codex exec`:

```
codex exec --workspace-write -m gpt-5-codex 'YOUR_PROMPT'
```

### 프롬프트 (재사용 가능, 한 번 복붙)

```text
당신은 Hostinger VPS 위 Paperclip + Hermes + Codex 스택의 설치·운영 자동화 보조자입니다. 사용자는 `paperclip-hermes-codex-on-hostinger/docs/manual-install-on-one-click-paperclip.md` 가이드를 따르고 있고, 당신은 그 가이드의 명령을 정확히 실행하여 사용자 부담을 줄입니다.

# 작업 원칙

1. **명령 전에 컨텍스트 검증**:
   - `docker ps`로 paperclip 컨테이너 이름 확인
   - `cat /docker/<project>/.env`로 ADMIN_PASSWORD·TRAEFIK_HOST·VPS_IP 확인
   - `tailscale status --peers=false --json`로 Tailscale FQDN 확인

2. **destructive 작업은 사용자 확인**: `docker compose down -v`, `rm -rf data/`, `tailscale logout` 등은 절대 자동 실행하지 말고 사용자에게 명시적 승인 요청.

3. **OAuth 단계는 사용자에게 위임**: hermes auth add openai-codex 같은 device-flow는 device URL/code를 사용자에게 그대로 보고하고 인증 완료 대기.

4. **시크릿 마스킹**: ADMIN_PASSWORD, TS_AUTHKEY, OPENAI_API_KEY, Codex/Hermes OAuth access_token은 항상 첫 8자 + ***으로 마스킹.

5. **함정 회피**:
   - `docker exec`에 항상 `--user node`
   - HOME은 /home/node여야 hermes가 auth.json 찾음
   - `/entrypoint`가 아니라 `/entrypoint.sh`
   - apt install은 sudo
   - .env 수정만으로 compose env가 안 바뀌면 docker-compose.yml의 environment 섹션이 hardcode — `${VAR:-default}` 형태로 패치
   - hermes-paperclip-adapter v0.2.x는 DEFAULT_MODEL fallback bug — sed patch가 init.sh에 있어야 영구

6. **각 STEP 끝에 검증 명령 실행**:
   - paperclip /api/health → 200 ok
   - hermes auth status openai-codex → logged in
   - hermes status | grep -E "Model|Provider" → 정확
   - 어댑터 sed 패치: grep -c "cfgString(config.model) || DEFAULT_MODEL" 결과 0

# 임무

가이드의 STEP 01부터 STEP 12까지 순서대로 진행. 각 STEP 시작 시 사용자에게 진행 의사 확인. STEP 끝마다 검증 결과를 한 줄로 요약. STEP 도중 에러 발생 시 Troubleshooting T1~T8 매칭 후 해당 fix 자동 적용. T1~T8 외 에러는 stack trace + 의심 원인 + 제안 fix 3가지로 사용자에게 보고.

가이드 위치: /docker/<project>/data/manual-install-on-one-click-paperclip.md (또는 git checkout한 곳).
```

---

## Paperclip CEO 운영 프롬프트

Paperclip UI에서 CEO agent에 새 issue 할당할 때 권장 prompt 패턴. agent의 AGENTS.md persona와 함께 사용.

### Issue title·body 권장 형식

```text
title: <한 문장 명확한 요청>
body:
## 배경
<왜 이 task가 필요한지 1-3줄>

## 입력
<재료가 되는 데이터·문서·이전 결정 링크>

## 출력 형식
<원하는 답변 구조 — bullet, 표, 절차 등>

## 제약
- 시간: <urgency>
- 리소스: <비용·도구 제약>
- 보안: <외부 공유 여부>

## 위임 권장
<특정 전문가 agent 호출이 필요하면 여기에 — 예: "데이터 분석은 'analyst' agent에게 위임">
```

### 예시 — 실제로 작동하는 형식

```
title: Q4 OKR 초안 작성

body:
## 배경
4분기 시작. 회사 전략 일관성 + 팀 우선순위 정렬 필요.

## 입력
- Q3 OKR 결과: /docs/q3-okr-retro.md
- 진행 중 프로젝트 3개: Paperclip 스택, Hermes 가이드 v2, AI 강의 신규 모듈

## 출력 형식
- 핵심 목표 3개 (Objective)
- 각 목표마다 측정 가능한 Key Result 2~3개
- 책임자(역할명)와 1차 마감

## 제약
- 시간: 2시간 reasoning
- 보안: 외부 공유 안 함

## 위임 권장
- 시장 분석 데이터가 필요하면 'researcher' 호출
- 코드 작성/리뷰가 필요하면 'engineer' 호출
- CEO는 의사결정·우선순위 결정·리뷰만
```

---

## Hostinger Update 버튼이 일어나면

호스팅어 Docker Manager의 "Update" 버튼은 본질적으로 `docker compose pull && docker compose up -d --force-recreate`. 다음이 일어남:

1. paperclip image의 새 :latest pull
2. 컨테이너 force-recreate
3. **컨테이너 안 변경(apt install, sed patch, /usr/local/bin/hermes symlink)은 사라짐**
4. **그러나 init.sh가 매 시작 시 자동 재적용** — host bind mount(`./data/tools/init.sh`)에 있고 entrypoint가 그걸 호출

⇒ 사용자 추가 작업 없이 복구. paperclip image가 update돼도 동작.

**예외**:
- docker-compose.yml 자체가 호스팅어 template으로 reset되면 STEP 03·05의 compose 수정이 사라짐. 그땐 STEP 03·05 다시 적용.
- `/docker/paperclip-<random>/data/tools/` 디렉터리는 호스팅어 update가 건드리지 않음 (data 마운트 영역).

따라서 가장 안전한 영구화 단위: **`data/tools/` 디렉터리에 모든 보조 binary + script를 두고, compose에는 그 디렉터리만 bind mount하는 형태**.

---

## 부록 — 발견된 8개 함정 요약표

| # | 증상 | 원인 | 해결 위치 |
|---|---|---|---|
| T1 | Console terminal stale ID | hPanel UI 캐시 | 페이지 새로고침 |
| T2 | hermes command not found | PATH 미노출 | init.sh 심볼릭 |
| T3 | hermes auth status logged out | HOME 차이 | --user node 명시 |
| T4 | apt install Permission denied | node not root | init.sh sudo |
| T5 | restart loop /entrypoint ENOENT | path typo | bash -c /entrypoint.sh |
| T6 | PAPERCLIP_PUBLIC_URL 갱신 안 됨 | hard-coded env in compose | sed `${VAR:-...}` |
| T7 | model=anthropic/claude-sonnet-4 spawn | adapter v0.2.1 DEFAULT_MODEL fallback | init.sh sed patch (mirror PR #123) |
| T8 | "Hermes isn't configured" | hermes config 미설정 | hermes config set 3줄 |
