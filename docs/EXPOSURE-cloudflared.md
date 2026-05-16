# Exposure: Cloudflare Tunnel

호스트의 80/443 포트를 안 열고 Cloudflare 엣지로 outbound 터널만 만들어 공개 URL 제공. NAT 뒤 노트북·Traefik 없는 VPS·DDoS 보호·IP 숨김이 필요한 시나리오.

## 전제

- Cloudflare 계정 (무료)
- Cloudflare에 등록된 도메인 (Cloudflare가 DNS NS를 관리)
- 본인 머신(노트북 또는 VPS)에 `cloudflared` 바이너리 (튜널 생성용 — 컨테이너는 우리가 띄움)

## cloudflared 설치 (호스트)

튜널 생성·DNS 라우팅 명령은 호스트의 `cloudflared`로 한 번만 실행합니다. 그 후 우리 compose가 사이드카로 띄우는 cloudflared가 실제 트래픽을 처리.

```bash
# macOS
brew install cloudflared

# Linux (Debian/Ubuntu)
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared

# Windows
# https://github.com/cloudflare/cloudflared/releases
```

## 튜널 생성 (일회성)

```bash
# 1. Cloudflare 계정으로 로그인 (브라우저 OAuth)
cloudflared tunnel login
# → ~/.cloudflared/cert.pem 생성됨

# 2. 튜널 생성
cloudflared tunnel create hermes-paperclip
# → 출력: Created tunnel hermes-paperclip with id <UUID>
# → ~/.cloudflared/<UUID>.json 생성됨 (credentials)

# 3. 3개 DNS 라우팅
cloudflared tunnel route dns hermes-paperclip tui.example.com
cloudflared tunnel route dns hermes-paperclip dash.example.com
cloudflared tunnel route dns hermes-paperclip paperclip.example.com
```

이제 Cloudflare DNS에 3개의 CNAME이 자동 등록됐고, 각각 튜널 UUID로 연결됩니다.

## 자격 파일 + config 복사

```bash
cd hermes-paperclip-on-hostinger

# 자격 파일 복사 (UUID는 cloudflared tunnel create 출력에서)
cp ~/.cloudflared/<UUID>.json ./cloudflared/

# config 생성
cp cloudflared/config.yml.example cloudflared/config.yml
```

`cloudflared/config.yml` 편집:

```yaml
tunnel: <UUID>
credentials-file: /etc/cloudflared/<UUID>.json

ingress:
  - hostname: tui.example.com
    service: http://hermes-tui:4860
  - hostname: dash.example.com
    service: http://hermes-dashboard:9119
  - hostname: paperclip.example.com
    service: http://paperclip:3100
  - service: http_status:404
```

## 설치

```bash
MODE=cloudflared \
  PROJECT_DOMAIN=example.com \
  ADMIN_EMAIL=you@example.com \
  ./setup.sh
docker compose up -d
```

`cloudflared` 사이드카가 부팅되어 Cloudflare 엣지에 outbound 터널을 dial out. 호스트의 80/443은 안 열림.

## 검증

```bash
# 사이드카 로그 — 튜널 연결 확인
docker compose logs cloudflared | tail -20
# → "Connection ... registered" 메시지

# 외부 HTTPS
PW=$(grep ADMIN_PASSWORD .env | cut -d= -f2)
curl -sS -o /dev/null -w "HTTP=%{http_code}\n" https://dash.example.com/
curl -sS -u "hermes:$PW" -o /dev/null -w "HTTP=%{http_code}\n" https://tui.example.com/
curl -sS -o /dev/null -w "HTTP=%{http_code}\n" https://paperclip.example.com/

# TLS 인증서 — Cloudflare가 자동 발급
echo | openssl s_client -servername dash.example.com \
  -connect dash.example.com:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer
```

## Cloudflare Access — 인증 게이트 추가 (선택)

기본은 공개 URL입니다. 누구나 도메인을 알면 접근 가능 (단, 각 서비스의 자체 인증을 통과해야). Cloudflare Access를 두면 페이지 진입 전에 이메일/OAuth 검증을 추가할 수 있습니다 — 무료 plan에서 최대 50명까지 정책 정의.

### 설정 흐름

1. Cloudflare 대시보드 → **Zero Trust** → **Access** → **Applications**
2. **Add application** → Self-hosted
3. Application domain: `dash.example.com` (또는 `tui.`, `paperclip.`)
4. Identity provider: email OTP (기본) 또는 Google·GitHub OAuth
5. Policy: 허용할 이메일 도메인/주소 지정 (예: `*@dante-labs.com`)
6. 저장

이후 해당 도메인에 누가 접근하면 Cloudflare Access 로그인 페이지가 먼저 뜸. 검증 후 우리 서비스로 통과.

같은 식으로 3개 서브도메인 각각 별도 정책 가능 (예: Paperclip은 더 좁은 허용 이메일).

## 트러블슈팅

### "No connection found" 또는 502/521

```bash
docker compose logs cloudflared | tail -30
```

- 자격 파일 경로 틀림 → `cloudflared/config.yml`의 `credentials-file`이 컨테이너 안 경로(`/etc/cloudflared/<UUID>.json`)인지 확인. 사이드카는 `./cloudflared:/etc/cloudflared:ro`로 마운트.
- `ingress` service URL이 잘못된 컨테이너명/포트 가리킴 → `docker compose ps`로 서비스 이름 확인.
- 사이드카가 같은 브리지 네트워크에 없음 → `docker network ls`로 `<project>_net` 확인.

### "Tunnel ... has no active connections"

방화벽이 cloudflared의 outbound를 막을 가능성. cloudflared는 7844/UDP·443/TCP outbound 사용. 사내 방화벽이라면 IT 팀에 cloudflare.com·trycloudflare.com outbound 허용 요청.

### DNS 라우팅이 작동 안 함

```bash
# cloudflared 측 정상 등록 확인
cloudflared tunnel route dns hermes-paperclip dash.example.com
# Already exists 메시지면 정상
```

Cloudflare 대시보드 → DNS에서 해당 CNAME 레코드가 `<UUID>.cfargotunnel.com` 가리키는지 확인.

### `cloudflared tunnel login`이 매번 새 로그인

`~/.cloudflared/cert.pem`이 cert로 한 번 발급되면 1년간 유효. 다른 머신에서 같은 튜널 운영하려면 cert.pem과 `<UUID>.json` 둘 다 복사.

## 한도와 가격

| 항목 | Free | Pro | Business |
|---|---|---|---|
| 튜널 개수 | 무제한 | 무제한 | 무제한 |
| 트래픽 | 무제한 | 무제한 | 무제한 |
| Cloudflare Access 사용자 | 50명 | 50명 | 무제한 |
| DDoS 보호 | ✅ | ✅ | ✅ |

개인+소팀 운영엔 Free로 충분.

## Tailscale vs Cloudflare Tunnel — 언제 어느 쪽?

| 시나리오 | 추천 |
|---|---|
| 공개 URL 필요 + 누구나 접근 OK | Cloudflare Tunnel |
| 공개 URL 필요 + 이메일/OAuth 게이트로 좁히기 | Cloudflare Tunnel + Access |
| 외부 노출 절대 금지, 인증된 디바이스만 | **Tailscale** |
| 모바일에서 친근하게 접근 | Tailscale (앱 한 번 켜면 끝) |
| DDoS 보호·IP 숨김이 중요 | Cloudflare Tunnel |
| Cloudflare 계정·도메인 없음 | Tailscale |

## 회수

```bash
docker compose down -v

# 튜널 자체 삭제
cloudflared tunnel delete hermes-paperclip

# Cloudflare 대시보드 DNS에서 3개 CNAME 수동 또는 API로 제거
```
