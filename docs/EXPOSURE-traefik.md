# Exposure: Traefik (public HTTPS)

공인 IP + 도메인이 있는 VPS에서 누구나(또는 Basic Auth로 가드된) 접근 가능한 공개 SaaS 모드. Hostinger Docker Manager가 이미 Traefik을 제공하므로 별도 설치 없이 라벨만 붙이면 됩니다.

## 전제

- VPS 공인 IP 있음
- 자기 도메인 있음 (Cloudflare 등 DNS 관리 가능)
- VPS에 Traefik이 이미 떠 있음 — Hostinger Docker Manager로 아무 원클릭 앱을 한 번 띄우면 자동으로 `traefik-*` 프로젝트가 깔립니다. 그 Traefik이 우리 라벨을 Docker 소켓 discovery로 자동 인식.

Traefik이 없는 VPS면 [traefik/README.md](../traefik/README.md)의 standalone 스택을 먼저 띄우세요.

## DNS 설정

3개 A 레코드, 모두 VPS 공인 IP로:

```
tui.hermes.example.com         A    156.67.219.3
dash.hermes.example.com        A    156.67.219.3
paperclip.hermes.example.com   A    156.67.219.3
```

Cloudflare를 쓴다면 **Proxy 상태는 DNS only (회색 구름)**. Cloudflare proxy를 켜면 Let's Encrypt HTTP-01 챌린지가 Cloudflare에 가로채여 실패합니다.

검증:
```bash
dig +short tui.hermes.example.com    # → VPS IP
dig +short dash.hermes.example.com   # → VPS IP
dig +short paperclip.hermes.example.com   # → VPS IP
```

## 설치

```bash
ssh root@<VPS-IP>
mkdir -p /docker/hermes-paperclip && cd /docker/hermes-paperclip
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/install.sh \
  | MODE=traefik PROJECT_DOMAIN=hermes.example.com ADMIN_EMAIL=you@example.com bash
```

`install.sh`가 끝나면 3개 도메인 모두 Let's Encrypt 인증서 자동 발급 (~10-30초).

## 검증

본인 노트북에서:

```bash
# 인증서 발급 확인
echo | openssl s_client -servername dash.hermes.example.com \
  -connect dash.hermes.example.com:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
# issuer가 "Let's Encrypt"이면 성공

# 외부 HTTPS
PW=$(ssh root@<VPS-IP> 'grep ADMIN_PASSWORD /docker/hermes-paperclip/hermes-paperclip-on-hostinger/.env | cut -d= -f2')

curl -sS -o /tmp/d.html -w "HTTP=%{http_code}\n" https://dash.hermes.example.com/
# → 200 + Hermes Dashboard HTML

curl -sS -u "hermes:$PW" -o /tmp/t.html -w "HTTP=%{http_code}\n" https://tui.hermes.example.com/
# → 200 + ttyd terminal

curl -sS -o /tmp/p.html -w "HTTP=%{http_code}\n" https://paperclip.hermes.example.com/
# → 200 + Paperclip
```

## Basic Auth 미들웨어 추가 (선택)

기본값은 **각 서비스 자체 인증**(Paperclip sign-up, ttyd basic-auth, Hermes session token)만 씁니다. 외부 봇·스캐너의 무차별 자격 시도를 더 막고 싶다면 Traefik basic-auth를 한 겹 더 둘 수 있습니다.

### APR1 해시 생성

```bash
ssh root@<VPS-IP> 'openssl passwd -apr1 "<choose-a-strong-password>"'
# 출력 예: $apr1$mm7dUVrC$C2dZKTa.NSX1K4Do08bHQ1
```

### docker-compose.traefik.yml 수정

Dashboard 서비스에 미들웨어 추가 (TUI·Paperclip은 자체 인증으로 충분):

```yaml
services:
  hermes-dashboard:
    labels:
      # ... 기존 라벨 ...
      - traefik.http.routers.${COMPOSE_PROJECT_NAME:-hermes-paperclip}-dash.middlewares=${COMPOSE_PROJECT_NAME:-hermes-paperclip}-dash-auth
      - traefik.http.middlewares.${COMPOSE_PROJECT_NAME:-hermes-paperclip}-dash-auth.basicauth.users=admin:$$apr1$$mm7dUVrC$$C2dZKTa.NSX1K4Do08bHQ1
```

> Compose는 라벨 안의 `$`를 변수 보간으로 해석. APR1 해시의 모든 `$`를 **`$$`로 이중 이스케이프** 필요. `docker inspect`로 보면 단일 `$`로 저장됩니다.

`docker compose up -d --force-recreate hermes-dashboard` 후 `curl https://dash.hermes.example.com/` → 401(`realm="traefik"`) 확인.

## IP 화이트리스트 미들웨어 (선택)

특정 IP/CIDR에서만 접근 허용:

```yaml
labels:
  - traefik.http.middlewares.${COMPOSE_PROJECT_NAME:-hermes-paperclip}-ipallow.ipallowlist.sourcerange=203.0.113.42/32,198.51.100.0/24
  # 라우터의 middlewares 체인에 추가 (콤마로 연결):
  - traefik.http.routers.${COMPOSE_PROJECT_NAME:-hermes-paperclip}-dash.middlewares=${COMPOSE_PROJECT_NAME:-hermes-paperclip}-ipallow,${COMPOSE_PROJECT_NAME:-hermes-paperclip}-dash-auth
```

미들웨어 체인 순서가 중요: IP 화이트리스트 먼저, 그 다음 basic-auth.

## 트러블슈팅

### `502 Bad Gateway`

```bash
docker compose ps                  # 컨테이너 상태
docker compose logs hermes-dashboard | tail -50
docker exec hermes-paperclip-hermes-dashboard-1 \
  sh -c 'curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:9119/'
```

- 내부 200, 외부 502 → 컨테이너가 `127.0.0.1` 바인딩이라 Traefik이 못 닿음. `--host 0.0.0.0` 확인.

### Let's Encrypt 인증서 미발급

```bash
docker logs <traefik-container> 2>&1 | grep -i acme | tail -20
```

흔한 원인:
- DNS A 레코드가 VPS 공인 IP 아님 → `dig` 다시 확인
- 80 포트 차단 → ACME HTTP-01 챌린지 실패
- **공유 도메인 rate limit** — `*.hstgr.cloud` 같은 Hostinger 호스트네임은 모든 고객이 50,000개/주 한도 공유. 자기 도메인 사용 강력 권장. (이 함정은 우리 [이전 가이드](../../hermes-dashboard/hostinger-hermes-dashboard-setup.md)에서 상세 다룸)

### 라벨 변경 후 Traefik이 인식 못 함

Traefik이 Docker 소켓 polling 주기에 따라 라벨 변경을 늦게 반영할 수 있음. `docker compose up -d --force-recreate hermes-dashboard`로 강제 재인식.

### Basic Auth 비밀번호 안 먹힘

`docker inspect`로 컨테이너 라벨 값 확인:

```bash
docker inspect <project>-hermes-dashboard-1 \
  --format '{{range $k,$v := .Config.Labels}}{{println $k "=" $v}}{{end}}' \
  | grep basicauth
```

값이 `admin:$apr1$...$...` (단일 `$`) 형식이어야 함. `$$`가 그대로 보이면 Docker Compose 버전 업그레이드 (v2.20+).

## 회수

```bash
docker compose down -v
cd .. && rm -rf hermes-paperclip-on-hostinger
```

Cloudflare DNS 3개 A 레코드 수동 또는 API로 제거.
