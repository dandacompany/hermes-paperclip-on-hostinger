# Paperclip → Hermes → Codex 단일 컨테이너 아키텍처 — Design Spec

- **Date:** 2026-05-17
- **Status:** Approved (brainstorming 완료, 구현 전)
- **Supersedes:** 현재 `hermes-paperclip-on-hostinger` 의 사이드카 구조
- **New repo name:** `paperclip-hermes-codex-on-hostinger`

## 1. 목적

Paperclip을 orchestrator로, Hermes Agent를 워커로, Codex CLI를 Hermes의 LLM 백엔드로 묶어 단일 Docker 컨테이너에서 운영한다. Hostinger Docker Manager의 "업데이트" 버튼 한 번으로 세 도구의 최신 버전이 자동 반영되며, 첫 부팅 시 admin 가입과 Hermes 부트스트랩이 자동화되고 Codex OAuth만 사용자가 1회 브라우저 인증한다.

## 2. 사용자 시점 동작

```
사용자 → Paperclip UI (port 3100)
         ↓ hermes_local 어댑터
         Hermes Agent CLI
         ↓ provider: codex_local
         Codex CLI (OAuth 토큰 or OPENAI_API_KEY)
         ↓
         OpenAI API → GPT-5/5.5 등
```

- Paperclip의 어댑터 환경 체크가 같은 컨테이너 PATH의 `hermes` 바이너리를 즉시 발견 → "Test now" 통과
- Hermes 인스턴스는 단일 — paperclip 워커용 인스턴스와 사람용 dashboard·TUI가 같은 `~/.hermes` 데이터를 공유
- Codex OAuth 토큰은 `/home/node/.codex/auth.json` named volume에 저장 → 이미지 업데이트해도 영구 보존

## 3. 컨테이너 구성

### 3.1 단일 컨테이너 안 프로세스

| 프로세스 | 포트 | 역할 | tini 아래 위치 |
|---|---|---|---|
| `paperclipai run` | 3100 | Paperclip orchestrator + Web UI | foreground (PID 1 직속) |
| `hermes dashboard` | 9119 | Hermes 세션/skills/API key 관리 SPA | background |
| `ttyd → hermes shell` | 4860 | 브라우저 안 Hermes 터미널 | background |
| Codex CLI | (n/a) | Hermes가 task별로 spawn | on-demand |

PID 1은 `tini -g`. SIGTERM은 process group 전체에 전파되어 모든 BG가 깔끔히 종료.

### 3.2 외부 컨테이너 (선택)

| 컨테이너 | 모드 | 역할 |
|---|---|---|
| `tailscale` | tailscale | Tailscale 메시 노출 사이드카 (`network_mode: service:tailscale`) |
| (없음) | local | `127.0.0.1` 직접 바인딩 |

Traefik / Cloudflared overlay는 v1 범위 밖. 안정화 후 별도 sprint.

## 4. 이미지 빌드

### 4.1 Multi-stage Dockerfile

```dockerfile
FROM ghcr.io/hostinger/hvps-hermes-agent:latest AS hermes
FROM ghcr.io/hostinger/hvps-paperclip:latest

USER root
COPY --from=hermes /usr/local/bin/hermes /usr/local/bin/hermes
COPY --from=hermes /usr/local/bin/ttyd  /usr/local/bin/ttyd
COPY --from=hermes /etc/hermes /etc/hermes
COPY ./scripts/entrypoint.sh   /entrypoint.sh
COPY ./scripts/supervisor.sh   /usr/local/bin/supervisor.sh
COPY ./scripts/codex-oauth.sh  /usr/local/bin/codex-oauth.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/supervisor.sh /usr/local/bin/codex-oauth.sh \
 && mkdir -p /paperclip /home/node/.hermes /home/node/.codex \
 && chown -R node:node /home/node/.hermes /home/node/.codex

USER node
EXPOSE 3100 9119 4860
ENTRYPOINT ["tini","-g","--","/entrypoint.sh"]
```

설계 원칙:
- Hermes 이미지에서 **바이너리·system config만** 복사. 데이터·credentials·인스턴스 디렉터리는 가져오지 않는다 (secret leak 방지).
- Paperclip base 이미지에 `codex` 바이너리가 이미 번들되어 있어 별도 install 없음.
- Codex CLI 0.122+가 `OPENAI_API_KEY` env를 자동으로 `auth.json`으로 변환 (Paperclip PR #5276) — API key 경로는 entrypoint 코드 0줄로 지원.

### 4.2 GHA workflow

`.github/workflows/build-and-push.yml`:

- Trigger: `schedule: '17 3 * * *'` (KST 12:17 매일) + `push` on Dockerfile/scripts + `workflow_dispatch`.
- Build: `docker/build-push-action@v6`, `platforms: linux/amd64`, `pull: true` (base `:latest` 강제 갱신), GHA cache.
- Tags: `:latest`, `:<sha>`, `:nightly-<run_number>`.
- 결과: 매일 KST 12:17에 paperclip/hermes/codex 최신 버전이 우리 이미지에 자동 반영. 호스팅어 콘솔 "업데이트" 버튼이 `docker compose pull && up -d` → 최신 디지스트 받아감.

## 5. Entrypoint + Auth Bootstrap

### 5.1 흐름

```
[1] permission fix (chown /paperclip /home/node/.hermes /home/node/.codex)
[2] Paperclip bootstrap
    config.json 없으면 → onboard --yes → ADMIN_* env로 sign-up → bootstrap-ceo invite accept
                       → disableSignUp:true 잠금 → onboard 종료
[3] Hermes bootstrap
    ~/.hermes/config.yaml 없으면 → /etc/hermes/template 복사
                                  → provider: codex_local 설정
                                  → session_token 생성 (deterministic hash)
                                  → .ttyd-creds 작성
[4] Codex auth detection (비차단, background)
    ├─ ~/.codex/auth.json 있음 → "✓ Codex auth: <mode>"
    ├─ OPENAI_API_KEY 있음     → "✓ Codex auth: API key" (CLI가 자동 변환)
    └─ 둘 다 없음              → codex login --device → URL/code stdout
                                Paperclip/Hermes는 부팅 계속, OAuth 완료 시 다음 task부터 동작
[5] supervisor.sh exec
    ├─ hermes dashboard &      (BG, 3회 재시작 후 give up)
    ├─ ttyd -p 4860 -c "$U:$P" hermes shell &
    └─ exec paperclipai run    (FG)
```

### 5.2 인증 항목 별 자동화 수준

| 항목 | 방식 | 사용자 개입 |
|---|---|---|
| Paperclip admin 가입 | `ADMIN_USERNAME/EMAIL/PASSWORD` env → entrypoint 자동 | 0 (env 채우면 끝) |
| Paperclip disableSignUp 잠금 | bootstrap 후 자동 sed | 0 |
| Hermes Dashboard 세션 토큰 | deterministic hash from `ADMIN_*` + machine-id | 0 |
| Hermes TUI basic-auth | `$ADMIN_USERNAME:$ADMIN_PASSWORD` | 0 |
| Hermes → Codex provider | `provider: codex_local` 자동 작성 | 0 |
| Codex OAuth | `codex login --device` 백그라운드 + 로그 URL | **1회 브라우저 클릭** |
| Codex API key (fallback) | `OPENAI_API_KEY` env | 0 (env 채우면 끝) |

### 5.3 비차단 부팅 원칙

OAuth 완료를 대기하지 않는다. Paperclip/Hermes UI는 OAuth와 무관하게 즉시 뜬다. Codex가 필요한 task만 일시 실패 → OAuth 완료 후 다음 task부터 자동 회복.

## 6. Compose 구성

### 6.1 파일 트리

```
paperclip-hermes-codex-on-hostinger/
├── docker-compose.yml              # base — paperclip-hermes-codex 서비스 + volumes
├── docker-compose.local.yml        # overlay — 127.0.0.1:{3100,9119,4860}
├── docker-compose.tailscale.yml    # overlay — tailscale 사이드카 + serve.json
├── docker-compose.console.yml      # self-contained (= base + tailscale) — Hostinger URL import 전용
├── tailscale/serve.json
├── Dockerfile
├── scripts/{entrypoint,supervisor,codex-oauth}.sh
├── .env.example
└── setup.sh                        # 로컬 사용자용 MODE 선택기
```

### 6.2 Volume 영속성

| Volume | Mount | 보존 항목 |
|---|---|---|
| `paperclip-data` | `/paperclip` | Paperclip 인스턴스·DB·로그 |
| `hermes-data` | `/home/node/.hermes` | Hermes 세션·skills·config |
| `codex-auth` | `/home/node/.codex` | Codex OAuth/API key 토큰 |
| `tailscale-state` | `/var/lib/tailscale` | Tailscale 노드 ID·키 |

`docker compose pull` 후 `up -d`는 컨테이너만 재생성하고 volume은 그대로 → 모든 인증·세션이 영구 보존된다.

### 6.3 노출 모드

- **local**: `127.0.0.1:3100/9119/4860` 직접 바인딩. 외부 접근 차단.
- **tailscale**: `network_mode: service:tailscale` + `tailscale serve` JSON으로 `.ts.net` FQDN의 :3100/:9119/:4860을 HTTPS로 노출. Tailscale magic cert 자동.

## 7. 호스팅어 콘솔 워크플로

1. **첫 배포**: hPanel → VPS → Docker Manager → "URL에서 컴포즈 가져오기" → `https://raw.githubusercontent.com/dandacompany/paperclip-hermes-codex-on-hostinger/main/docker-compose.console.yml` → 환경변수 폼 입력 → 배포.
2. **첫 사용**: 컨테이너 로그 패널 → Codex OAuth URL 발견 → 브라우저로 인증 1회 → 끝.
3. **업데이트**: 콘솔의 "업데이트" 버튼 클릭 → 새 이미지 pull + 컨테이너 재생성 → volume에 살아있는 인증·세션 그대로.
4. **롤백**: 콘솔 또는 SSH로 `image:` 태그를 `:nightly-<N>` 또는 `:<sha>`로 명시 → 특정 빌드 복귀.

## 8. Migration 계획

### 8.1 단계

```
[1] add-only 진입
    Dockerfile + scripts/ + .github/workflows/build-and-push.yml 추가
    구 사이드카 파일은 그대로. 첫 GHA 빌드로 GHCR 이미지 생성.
    구 사용자 영향 0.

[2] 동작 검증
    Mac: docker-compose.local.yml E2E (paperclip → hermes → codex 체인)
    Hostinger 스테이징: docker-compose.console.yml URL import 검증

[3] v0.1-sidecar 태그
    git tag -a v0.1-sidecar -m "Final sidecar release"
    git push origin v0.1-sidecar
    → 구 튜토리얼·영상 시청자가 영구 참조

[4] main rewrite
    제거: docker-compose.{traefik,cloudflared}.yml, hermes-* service 정의,
          docs/tutorial-* (구 파일들)
    추가: 새 compose 4종, 새 README, 새 .env.example, 새 setup.sh

[5] Repo rename
    hermes-paperclip-on-hostinger → paperclip-hermes-codex-on-hostinger
    (GitHub Settings → Rename, 자동 redirect)

[6] 새 튜토리얼 작성 (별도 sprint, 코드 안정화 후)
    docs/tutorial-hostinger-console/ — 11 step
    docs/tutorial-ssh-cli/             — 10 step
```

### 8.2 호환성 보장

| 항목 | 영향 | 보장 |
|---|---|---|
| 구 GitHub URL | 자동 redirect | GitHub 표준 |
| 구 GHCR 이미지 `ghcr.io/hostinger/hvps-*` | 영향 0 | upstream 직접 참조 안 함 |
| 구 docker-compose.yml | v0.1-sidecar 태그로 참조 | `git checkout v0.1-sidecar` |
| 운영 중 사이드카 사용자 | 자발적 마이그레이션 가이드 | `docs/MIGRATION-v0.1-to-v1.md` |

## 9. 새 튜토리얼 범위

### 9.1 `docs/tutorial-hostinger-console/` (11 step)

```
01 hPanel → VPS → Docker Manager
02 URL에서 컴포즈 가져오기
03 환경변수 입력 (ADMIN_*, TS_*, OPENAI_API_KEY는 비워두기)
04 배포 + 컨테이너 2개 상태 확인
05 Tailscale FQDN 확인 + PAPERCLIP_PUBLIC_URL 재배포
06 첫 접속 → Paperclip 로그인 (admin 자동 생성)
07 Hermes Dashboard 확인
08 Codex OAuth 부트스트랩 (콘솔 로그 → URL → 브라우저 인증)
09 첫 CEO 에이전트 생성 + "Test now" 통과 확인
10 첫 Task 실행 → 체인 검증
11 업데이트 흐름 (콘솔 Update 버튼)
```

### 9.2 `docs/tutorial-ssh-cli/` (10 step)

```
01 VPS 구입 + SSH 키
02 git clone + setup.sh (MODE: local | tailscale)
03 .env 입력
04 docker compose up -d
05 첫 로그인 + Hermes Dashboard 검증
06 Codex OAuth (docker logs → URL)
07 첫 CEO 에이전트 + Test now
08 Task 실행 + 체인 검증
09 업데이트 (compose pull + up -d)
10 백업/복원 (volume 단위)
```

## 10. 비-기능 요구사항

- **Secret leak 방지**: pre-commit + gitleaks 룰셋 그대로 유지. Codex `auth.json`은 named volume에만 저장, 호스트 파일시스템·git에는 절대 노출 안 됨.
- **이미지 재현성**: 모든 빌드는 GHA에서만. 로컬 수동 push 금지. `:<sha>` 태그가 immutable 참조.
- **단일 컨테이너 메모리 footprint**: paperclip ~600MB + hermes ~100MB + ttyd ~10MB ≈ 750MB. Hostinger KVM 2 (2GB) 이상 권장 (README에 명시).
- **백업**: volume 4종 `docker run --rm -v <vol>:/data -v $PWD:/out alpine tar czf /out/<vol>.tgz /data` 패턴으로 사용자가 직접. v1.x 안에서 자동 백업 cron은 범위 밖.

## 11. Out of Scope (v1)

- Traefik / Cloudflared overlay
- 자동 백업 cron
- Hermes ↔ 다른 LLM provider (Anthropic Claude, OpenRouter, Gemini) 기본 지원 — v1은 Codex만. 사용자가 `~/.hermes/config.yaml`을 수동 편집해서 변경은 가능하지만 entrypoint가 자동 설정하지 않음.
- Paperclip 다중 instance (`PAPERCLIP_INSTANCE_ID` ≠ default)
- 비-amd64 플랫폼 (Apple Silicon은 Docker Desktop Rosetta로만 지원)
- 자동 인증서 갱신 (Traefik/CF 사용 시 필요하지만 v1 범위 밖)
- GPT-5.5 모델 dropdown 표시 (upstream Issue #4481 머지 대기, OPENAI_API_KEY 우회는 튜토리얼에 안내)

## 12. 검증 기준

이 spec의 구현이 완료된 것으로 간주하려면:

1. `docker compose -f docker-compose.console.yml up -d` (env 채운 상태)로 Hostinger VPS에 1회 배포 후 콘솔 Update 버튼 1회 클릭만으로 paperclip/hermes/codex 모든 컴포넌트가 최신 버전으로 갱신되고 admin·OAuth 세션은 유지된다.
2. Paperclip UI에서 "Hermes Agent" 어댑터로 CEO 에이전트 생성 → "Test now"가 통과 (PATH 에러 없음).
3. Codex OAuth는 첫 부팅 시 컨테이너 로그에 URL이 나오고, 1회 브라우저 인증으로 영구 동작. 컨테이너 재시작/이미지 업데이트 시 재인증 불필요.
4. 단순 task 1개("Hello world" 등)가 Paperclip → Hermes → Codex 체인을 통과하여 실행 결과가 Paperclip UI에 반환된다.
5. 새 튜토리얼 2개가 처음 사용자도 막힘 없이 STEP 끝까지 따라갈 수 있다 (실 시뮬레이션 1회 완료).

## 13. 다음 단계

- 이 spec이 사용자 승인되면 `superpowers:writing-plans` 스킬로 TDD 기반 구현 플랜 작성
- 구현 플랜은 위 §8.1의 7단계를 각각 PR 단위로 쪼개고, 각 PR마다 검증 기준 명시
