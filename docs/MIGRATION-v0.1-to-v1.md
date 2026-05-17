# v0.1 사이드카 → v1 단일 컨테이너 마이그레이션

## 무엇이 바뀌었나

| 항목 | v0.1 사이드카 | v1 단일 컨테이너 |
|---|---|---|
| 컨테이너 수 | 4개 (hermes-dashboard, hermes-tui, paperclip, 노출 사이드카) | 2개 (paperclip-hermes-codex, tailscale) |
| Hermes 인스턴스 | dashboard + tui 별도 | 단일 프로세스 (포트 9119 + 4860) |
| 이미지 소스 | 개별 upstream 이미지 | `ghcr.io/dandacompany/paperclip-hermes-codex:latest` (nightly 빌드) |
| 노출 모드 | traefik / cloudflared / tailscale / local (4종) | local / tailscale (2종) |
| Codex | 없음 | 포함 (OAuth 1회 인증 필요) |

---

## 데이터 이전

### 1. 볼륨 이름 확인

```bash
# v0.1 볼륨 목록 확인 (프로젝트명에 따라 prefix가 다름)
docker volume ls | grep -E "hermes|paperclip"
```

### 2. Paperclip 데이터 내보내기

```bash
# v0.1 paperclip 볼륨에서 tar 추출
docker run --rm \
  -v <old_paperclip_volume>:/src:ro \
  -v "$(pwd)":/out \
  alpine tar czf /out/paperclip-backup.tar.gz -C /src .
```

### 3. v1 볼륨으로 가져오기

```bash
# v1 스택을 한 번 올려 볼륨 초기화 후 내려둠
docker compose up -d && docker compose down

# paperclip-hermes-codex 프로젝트의 paperclip-data 볼륨에 복원
docker run --rm \
  -v paperclip-hermes-codex_paperclip-data:/dst \
  -v "$(pwd)":/backup \
  alpine sh -c "cd /dst && tar xzf /backup/paperclip-backup.tar.gz"
```

### 4. Hermes 데이터 (선택)

v0.1의 Hermes 설정(`~/.hermes/config.yaml`, API Keys 등)도 동일한 방식으로
`hermes-hermes-data` → `paperclip-hermes-codex_hermes-data` 볼륨으로 이전 가능합니다.
단, v1 첫 부팅 시 ADMIN_* 변수로 새 계정이 자동 생성되므로 빈 볼륨으로 시작해도 무방합니다.

---

## 인증

### Admin 자격증명

`.env`의 `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD`는 v0.1과 동일한 값을 사용하면
Paperclip 계정과 Hermes 세션이 첫 부팅 시 자동으로 재생성됩니다.

### Codex OAuth (신규 요건)

v1은 Codex LLM 오케스트레이터를 포함하므로 OpenAI OAuth 인증이 1회 필요합니다.

```bash
# 컨테이너 로그에서 OAuth URL 확인
docker compose logs -f paperclip-hermes-codex | grep "Codex"
```

브라우저로 해당 URL 열어 로그인 완료 → 이후 재시작 시 자동 갱신됩니다.
`OPENAI_API_KEY`를 `.env`에 설정하면 OAuth 없이 API Key 모드로 동작합니다.

---

## 롤백

사이드카 구조로 돌아가려면 v0.1-sidecar 태그를 체크아웃하세요.
볼륨 이름이 충돌하지 않도록 v1 스택을 완전히 내린 후 진행합니다.

```bash
# v1 스택 완전 종료 (볼륨 유지)
docker compose down

# v0.1 코드로 전환
git checkout v0.1-sidecar

# v0.1 스택 실행
docker compose up -d
```

볼륨명 충돌이 예상되면 v1 스택 종료 시 `-v` 플래그로 볼륨까지 삭제하거나,
`COMPOSE_PROJECT_NAME`을 다르게 설정해 격리하세요.
