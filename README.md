# hermes-paperclip-on-hostinger

[Hermes Agent](https://github.com/NousResearch/hermes-agent)와 [Paperclip](https://www.hostinger.com/kr/vps/docker/paperclip)을 **사이드카로 묶어** 한 Docker 브리지 네트워크에서 같이 띄우는 OSS 스택입니다. 두 시스템이 호스트 IP·외부 토큰 교환 없이 `http://paperclip:3100`, `http://hermes-dashboard:9119`로 직접 통신할 수 있어, Paperclip이 작업을 분배하고 Hermes가 실행하는 **에이전트 오케스트레이션 파이프라인**을 한 인스턴스에서 운영할 수 있습니다.

원본 이미지는 그대로 사용합니다 (포크 없음):
- `ghcr.io/hostinger/hvps-hermes-agent:latest`
- `ghcr.io/hostinger/hvps-paperclip:latest`

> **Apple Silicon Mac 사용자**: 두 이미지는 amd64-only라 Docker Desktop의 Rosetta 2 emulation으로 돕니다. Settings → General → "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" 체크 (Docker Desktop 4.16+). compose 파일에 `platform: linux/amd64`가 박혀 있어 자동 처리됩니다.

## 3가지 인터페이스

| 인터페이스 | 컨테이너 포트 | 인증 | 용도 |
|---|---|---|---|
| **Hermes Dashboard** | 9119 | Hermes 자체 세션 토큰 | 그래픽 SPA — Sessions / API Keys / Skills 관리 |
| **Hermes TUI** | 4860 | ttyd HTTP Basic Auth | 브라우저 안의 터미널 콘솔 |
| **Paperclip Web** | 3100 | Paperclip 자체 sign-up + 쿠키 세션 | 작업·라우틴·승인 워크플로 |

## 4가지 노출 모드

한 저장소에서 `COMPOSE_FILE` 오버레이로 전환합니다. 개인·팀 비공개 운영이 기본 가정이라 **tailscale**이 권장 디폴트.

| 모드 | 어디서 쓰나 | 본인 호스트 | 외부 접근 | 도메인·TLS |
|---|---|---|:-:|:-:|
| **tailscale** ★ | 개인·팀 비공개 (로컬·VPS 공통) | `127.0.0.1` 직접 | Tailscale 메시 멤버만 | `.ts.net` 자동 |
| **local** | 본인만 사용, 외부 차단 | `127.0.0.1` 직접 | ❌ | 불필요 |
| **traefik** | 공개 SaaS, 도메인+공인 IP 있는 VPS | (포트 노출 없음) | 누구나 (HTTPS+Basic Auth) | 필요 (3개 서브) + LE 자동 |
| **cloudflared** | NAT 뒤 노트북, DDoS·IP숨김 원할 때 | (포트 노출 없음) | Cloudflare Access 정책 | 필요 (3개 서브) + CF 자동 |

각 모드의 상세는 [`docs/EXPOSURE-tailscale.md`](docs/EXPOSURE-tailscale.md) · [`traefik`](docs/EXPOSURE-traefik.md) · [`cloudflared`](docs/EXPOSURE-cloudflared.md).

## 빠른 설치

### Tailscale 모드 (권장 — 로컬·VPS 공통)

전제: [Tailscale](https://tailscale.com) 가입 (개인 무료, 100 디바이스). 사용자 본인과 공유할 사람들의 디바이스에 Tailscale 클라이언트 깔려 있음.

```bash
# 1. https://login.tailscale.com/admin/settings/keys 에서 auth key 발급
git clone https://github.com/dandacompany/hermes-paperclip-on-hostinger.git
cd hermes-paperclip-on-hostinger
MODE=tailscale TS_AUTHKEY=tskey-auth-... ADMIN_EMAIL=you@example.com ./setup.sh
docker compose up -d
```

접근 경로:
- **본인 호스트** (노트북이든 VPS든 같음): `http://127.0.0.1:9119` / `:4860` / `:3100`
- **메시 멤버** (모바일·동료): `https://<TS_HOSTNAME>.<your-tailnet>.ts.net:9119` / `:4860` / `:3100`

> 본인 호스트는 Tailscale 클라이언트가 깔려 있을 필요 없습니다 — 그냥 자기 컨테이너에 localhost로 직접 접근. 메시는 외부 접근 전용. macOS Docker Desktop도 동일하게 작동.

### 로컬 모드 (외부 차단, 본인만)

```bash
MODE=local ADMIN_EMAIL=you@example.com ./setup.sh
docker compose up -d
```

`http://127.0.0.1:{9119,4860,3100}` — LAN조차 안 보임.

### 공개 모드 (Traefik 또는 Cloudflare Tunnel)

공개 SaaS로 띄우거나 외부 클라이언트 접근이 필요한 경우. 자세한 흐름은 각 docs:
- [`docs/EXPOSURE-traefik.md`](docs/EXPOSURE-traefik.md) — Hostinger VPS 등 Traefik 있는 서버
- [`docs/EXPOSURE-cloudflared.md`](docs/EXPOSURE-cloudflared.md) — NAT 뒤·DDoS 보호·CF Access

## 구성 한눈에

```
                ┌──── exposure (mode-dependent) ────┐
                │                                   │
        Traefik / Cloudflare Tunnel / 127.0.0.1
                │                                   │
   ┌────────────┼──────────────────┬────────────────┤
   │            │                  │                │
hermes-tui   hermes-dashboard   paperclip       (gateway, opt-in)
 :4860        :9119              :3100              ―
   │            │                  │                │
   └─── hermes-data (vol) ─────────┤                │
                                   └── paperclip-data (vol)

   ────── shared bridge network (hermes-paperclip_net) ──────
            └ hermes containers can call http://paperclip:3100
            └ paperclip can call http://hermes-dashboard:9119
```

## 인증 모델

각 시스템이 **자체 인증을 가짐**. 추가 reverse-proxy basic-auth는 기본값으로 안 붙입니다 — 사용자 경험 일관성 + 이중 로그인 회피.

- **Paperclip**: 첫 실행 시 `ADMIN_EMAIL/PASSWORD`로 자동 sign-up, 그 이후 쿠키 세션
- **Hermes Dashboard**: HTML에 주입되는 `__HERMES_SESSION_TOKEN__` 단방향 토큰 + API 검증
- **Hermes TUI (ttyd)**: HTTP Basic Auth (ttyd 옵션 `-c USER:PASS`)

> Hermes Dashboard가 공개 도메인에 노출될 때 추가 가드가 필요하면 [docs/EXPOSURE-traefik.md](docs/EXPOSURE-traefik.md)에 Traefik basic-auth middleware 적용 예시가 있습니다.

## 사이드카가 주는 이득

같은 Docker 브리지 네트워크 안에 있으니:

- Paperclip이 heartbeat 시 주입하는 짧은 JWT(`PAPERCLIP_API_KEY`)만으로 Hermes 컨테이너가 `http://paperclip:3100/api/...` 직접 호출
- Hermes가 작업 결과를 Paperclip의 task comment로 거꾸로 post
- 토큰 교환·OAuth flow 없이 single-tenant 자가 호스팅에 최적
- 두 데이터 볼륨(`hermes-data`, `paperclip-data`)이 독립적이라 한 쪽 재설치가 다른 쪽에 영향 없음

## 메시징 게이트웨이 (옵션)

Hermes가 Slack/Telegram/Discord에 응답하도록 하려면:

1. Dashboard 또는 TUI에서 `hermes setup` 한 번 실행 (config.yaml 생성)
2. 게이트웨이 enable:
   ```bash
   docker compose --profile gateway up -d
   ```

중지: `docker compose --profile gateway down`

## 비밀번호 회전

```bash
./setup.sh --rotate
docker compose up -d --force-recreate hermes-tui hermes-dashboard paperclip
```

## 라이선스

MIT. 두 원본 이미지(Hermes / Paperclip)의 라이선스는 각자 제작사를 따릅니다 — 이 저장소는 이미지를 재배포하지 않고 **사용 방법(사이드카 구성)만** 배포합니다.

## 문서

- **[docs/tutorial-hermes-paperclip-on-hostinger/](docs/tutorial-hermes-paperclip-on-hostinger/)** — 한 페이지 정적 HTML 튜토리얼 (Tailscale 모드 기준 8-step 워크스루). 빌드: `python3 build_tutorial_hermes_paperclip_on_hostinger.py`
- [docs/EXPOSURE-tailscale.md](docs/EXPOSURE-tailscale.md) — Tailscale 메시 VPN 매뉴얼 (권장 디폴트)
- [docs/EXPOSURE-traefik.md](docs/EXPOSURE-traefik.md) — Traefik 모드 상세 (Hostinger VPS 워크스루)
- [docs/EXPOSURE-cloudflared.md](docs/EXPOSURE-cloudflared.md) — Cloudflare Tunnel 설정
- [docs/INTEGRATION.md](docs/INTEGRATION.md) — Hermes ↔ Paperclip 연동 패턴
