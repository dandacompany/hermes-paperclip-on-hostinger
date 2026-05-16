# Exposure: Tailscale (recommended)

개인+팀 비공개 운영의 디폴트 모드. 같은 compose가 로컬 노트북·VPS 어디서나 동일하게 작동하고, 본인 호스트는 `127.0.0.1`로 직접·외부는 메시 멤버만 도달합니다.

## 왜 Tailscale인가

- **공개 노출 0** — `*.ts.net` 도메인은 메시 외부에서 도달 불가. 포트 스캔 안 됨.
- **인증 = 멤버십** — 누가 들어왔는지 Tailscale 콘솔에서 한눈에. invite/revoke가 클릭 한 번.
- **TLS 자동** — `.ts.net` 도메인용 Let's Encrypt 인증서를 Tailscale이 자동 발급·리뉴 (hstgr.cloud 같은 공유 도메인 rate limit 함정 없음).
- **모바일 일급 시민** — iOS/Android 앱으로 같은 메시 접근.
- **로컬·VPS 한 compose** — 노트북에서 띄우든 Hostinger VPS에서 띄우든 동일 yaml. 본인 호스트는 호스트 OS에 Tailscale 안 깔아도 됨 (127.0.0.1로 직접 접근).

## 사전 준비

### 1. Tailscale 계정

- [tailscale.com](https://tailscale.com) 가입 (개인 무료 plan = 100 디바이스 / 3 user). 팀이면 Starter $5/user/월.
- 본인 + 공유할 팀원 디바이스에 Tailscale 클라이언트 설치. 같은 tailnet에 가입.

### 2. Auth key 발급

[https://login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys) → **Generate auth key**.

| 옵션 | 권장 값 | 이유 |
|---|---|---|
| Reusable | ON | 사이드카 재생성 시 같은 키로 재가입 |
| Ephemeral | OFF | OFF면 컨테이너가 죽어도 노드가 메시에 남음 → 디바이스 목록 안정적. ON으로 두면 깨끗하지만 디버깅 어려움 |
| Pre-authorized | ON | 자동 승인. OFF면 매 가입 시 콘솔에서 수동 승인 필요 |
| Expiration | 90일 또는 그 이상 | 만료 후 재발급하면 .env만 갱신 |
| Tags | (옵션) | ACL 그룹 운영 시 |

발급된 `tskey-auth-XXXXX...`를 저장.

## 설치

### 노트북 (Mac/Windows/Linux)

```bash
git clone https://github.com/dandacompany/hermes-paperclip-on-hostinger.git
cd hermes-paperclip-on-hostinger
MODE=tailscale \
  TS_AUTHKEY=tskey-auth-XXXXX... \
  ADMIN_EMAIL=you@example.com \
  ./setup.sh
docker compose up -d
```

`install.sh`가 부팅 후 자동으로 사이드카의 실제 tailnet FQDN을 알아내 Paperclip의 `PUBLIC_URL`을 갱신합니다.

### VPS (Hostinger 등)

```bash
ssh root@<VPS-IP>
mkdir -p /docker/hermes-paperclip && cd /docker/hermes-paperclip
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/install.sh \
  | MODE=tailscale TS_AUTHKEY=tskey-auth-XXX... ADMIN_EMAIL=you@example.com bash
```

VPS 공인 IP가 있어도 **80/443은 열리지 않습니다** — Hermes/Paperclip 포트는 메시 안에서만 LISTEN. `nmap <VPS-IP>` 해도 SSH(22) 외엔 안 보입니다.

## 부팅 후 검증

```bash
# 1. 사이드카가 메시에 등록됐는지
docker compose exec tailscale tailscale status
#   → IP 100.x.x.x 할당, "active" 상태 확인

# 2. 실제 tailnet FQDN
docker compose exec tailscale tailscale status --json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'])"
#   → 예: hermes-paperclip.tail7b1307.ts.net.

# 3. 본인 호스트에서 (메시 안 거치고 직접)
curl http://127.0.0.1:9119/         # → 200
curl -u hermes:<PW> http://127.0.0.1:4860/   # → 200

# 4. 다른 메시 멤버(폰·동료)에서 — Tailscale 클라이언트 켜고
#    브라우저 또는 curl:
curl https://hermes-paperclip.<your-tailnet>.ts.net:9119/   # → 200
```

브라우저 접근:
- Dashboard: `https://<TS_HOSTNAME>.<your-tailnet>.ts.net:9119`
- TUI: `https://<TS_HOSTNAME>.<your-tailnet>.ts.net:4860` (ttyd basic-auth: `hermes` / `<PW>`)
- Paperclip: `https://<TS_HOSTNAME>.<your-tailnet>.ts.net:3100` (Paperclip sign-in: `<ADMIN_EMAIL>` / `<PW>`)

## 팀원 초대

[https://login.tailscale.com/admin/users](https://login.tailscale.com/admin/users) → **Invite users** → 이메일.

초대받은 사람이:
1. Tailscale 가입 (또는 Google·GitHub OAuth)
2. 본인 디바이스에 Tailscale 클라이언트 설치
3. 같은 tailnet에 자동 가입
4. 즉시 `https://<TS_HOSTNAME>.<your-tailnet>.ts.net:9119` 접근 가능 (별도 비밀번호 추가 안 필요 — 단, Hermes/Paperclip 자체 로그인은 필요)

### 회수

[https://login.tailscale.com/admin/users](https://login.tailscale.com/admin/users) → 해당 사용자 → **Remove**. 즉시 메시에서 빠짐.

## ACL — 누가 어디 접근하나 (선택)

[https://login.tailscale.com/admin/acls](https://login.tailscale.com/admin/acls)에서 JSON으로 세밀 제어.

기본은 같은 tailnet 멤버끼리 다 보임. 다음 같이 좁힐 수 있습니다:

```json
{
  "tagOwners": {
    "tag:hermes-paperclip": ["autogroup:admin"]
  },
  "acls": [
    // admin은 모든 노드 접근
    {"action": "accept", "src": ["autogroup:admin"], "dst": ["*:*"]},
    // 일반 멤버는 hermes-paperclip 노드의 9119/3100만 (4860 TUI는 차단)
    {"action": "accept", "src": ["autogroup:member"], "dst": ["tag:hermes-paperclip:9119,3100"]}
  ]
}
```

사이드카에 태그를 붙이려면 `docker-compose.tailscale.yml`의 `TS_EXTRA_ARGS`에 `--advertise-tags=tag:hermes-paperclip` 추가.

## 트러블슈팅

### "Paperclip이 BetterAuthError: Invalid base URL로 죽음"

`PAPERCLIP_PUBLIC_URL`이 placeholder 상태. `install.sh`가 자동 fix하지만 만약 실패했다면:

```bash
./scripts/refresh-tailnet.sh
```

수동으로 하려면 `.env`의 `PAPERCLIP_PUBLIC_URL`을 실제 FQDN으로 갱신 후 `docker compose up -d paperclip`.

### "메시 멤버에서 도달 안 됨 — Connection refused"

```bash
docker compose exec tailscale tailscale status   # 등록 확인
docker compose exec tailscale tailscale serve status   # serve 라우팅 확인
```

- 사이드카가 메시 가입 안 됨 → `TS_AUTHKEY` 유효 확인, 콘솔에서 만료/revoke 여부.
- serve 라우팅 비어 있음 → `tailscale/serve.json` 마운트 확인.

### "MagicDNS가 멤버 디바이스에서 안 풀림"

해당 디바이스의 Tailscale 설정에서 MagicDNS 토글 ON 확인. 또는 메시 IP로 직접 접근:

```bash
curl https://100.71.157.47:9119/   # IP로 직접 (cert SNI mismatch warning 가능)
```

### "NordVPN Meshnet과 충돌"

호스트 OS에 둘 다 깔린 경우만 해당. 우리 사이드카는 자기 컨테이너 namespace에서 작동하므로 호스트의 NordVPN과 직접 충돌 없음. 호스트에 둘 다 띄우는 경우는 [ZimaBoard2의 entrypoint nftables 패치 패턴](https://tailscale.com/kb/1338/nordvpn-conflict) 참고.

### "Mac에서 다른 tailnet에 가입되어 있음"

Mac의 `tailscale status`로 확인. 다른 계정 tailnet에 있으면 hermes-paperclip 안 보임:

```bash
tailscale logout
tailscale up   # 브라우저 OAuth로 datapod.k@... 계정 선택
```

`tailscale switch` 명령으로 계정 전환도 가능 (Tailscale 1.50+).

## 호스트 OS에 Tailscale을 깔고 싶다면

본인이 호스팅하는 노트북/VPS 자체도 메시 멤버로 만들고 싶을 때만 필요합니다. 컨테이너에서 작동하는 우리 사이드카와는 **독립적인 별개 설치**.

```bash
# macOS
brew install --cask tailscale
# Linux (apt-based)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Windows
# https://tailscale.com/download/windows
```

이 경우 호스트가 메시에서 보이게 되어 다른 멤버가 호스트 SSH도 메시 통해 접근 가능 (`tailscale ssh`). 우리 사이드카와 충돌 없음.

## 회수

```bash
docker compose down -v
cd .. && rm -rf hermes-paperclip-on-hostinger
```

Tailscale 콘솔에서 노드 제거: [https://login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) → `hermes-paperclip` → **Remove**.
