# paperclip-hermes-codex — v1 단일 컨테이너

Paperclip(작업 분배·승인 워크플로) + Hermes(에이전트 런타임) + Codex(LLM 오케스트레이터)를
**단일 컨테이너**에 통합한 OSS 스택입니다. GitHub Actions nightly 빌드로 세 도구의 최신 버전이
자동으로 이미지에 반영되며, Hostinger 콘솔 "업데이트" 버튼 한 번으로 즉시 적용됩니다.
첫 부팅 시 ADMIN_* 환경변수로 Paperclip·Hermes 계정이 자동 생성되고, Codex OAuth 인증은
컨테이너 로그에 출력된 URL로 브라우저 1회만 처리하면 됩니다.

> **Note:** Repo will be renamed to `dandacompany/paperclip-hermes-codex-on-hostinger` in PR 5.
> URLs using the old name may 404 until then.

---

## 3가지 인터페이스

| 인터페이스 | 포트 | 인증 방식 | 용도 |
|---|---|---|---|
| Paperclip Web | 3100 | Paperclip sign-up + 쿠키 세션 | 작업 라우팅·승인 워크플로 |
| Hermes Dashboard | 9119 | Hermes 세션 토큰 (ADMIN_* 자동 생성) | SPA — Sessions / API Keys / Skills 관리 |
| Hermes TUI | 4860 | ttyd HTTP Basic Auth (ADMIN_* 공용) | 브라우저 안의 터미널 콘솔 |

---

## 2가지 노출 모드

| 모드 | 바인딩 | 외부 접근 | TLS |
|---|---|---|---|
| local | 127.0.0.1 (포트 3100/9119/4860) | 불가 | 불필요 |
| tailscale | 컨테이너 내부망 (tailscale 사이드카) | Tailscale 메시 멤버만 | .ts.net 자동 HTTPS |

---

## 빠른 설치 (Hostinger 콘솔)

1. Hostinger VPS 패널 -> Docker Manager -> "URL에서 컴포즈 가져오기"
2. `docker-compose.console.v1.yml` Raw URL 붙여넣기
3. 환경변수 폼에서 값 입력 (ADMIN_EMAIL, ADMIN_PASSWORD 필수; 나머지는 기본값 사용 가능)
4. "배포" 클릭 -> 컨테이너 로그에서 Codex OAuth URL 확인 -> 브라우저 인증 1회

완료 후 `http://<VPS-IP>:3100` 으로 Paperclip에 접속합니다.

---

## 빠른 설치 (로컬 / SSH)

```bash
git clone https://github.com/dandacompany/paperclip-hermes-codex-on-hostinger.git
cd paperclip-hermes-codex-on-hostinger

# local 모드 (127.0.0.1 바인딩, 외부 차단)
MODE=local ADMIN_EMAIL=you@example.com ./setup.v1.sh

# .env 검토 후 실행
docker compose up -d
```

tailscale 모드를 사용하려면:

```bash
MODE=tailscale TS_AUTHKEY=tskey-auth-... TS_HOSTNAME=paperclip ./setup.v1.sh
docker compose up -d
```

---

## 업데이트

**Hostinger 콘솔:** Docker Manager -> 서비스 선택 -> "업데이트" 버튼 클릭.
최신 이미지를 pull하고 컨테이너를 재시작합니다.
volume에 살아있는 인증·세션이 그대로 유지됩니다.

**로컬 / SSH:**

```bash
docker compose pull
docker compose up -d
```

---

## v0.1 사이드카 구조 사용자

사이드카(2-컨테이너) 구조의 v0.1 태그는 별도로 유지됩니다:

```bash
git checkout v0.1-sidecar
```

v0.1 -> v1 마이그레이션 절차는 `docs/MIGRATION-v0.1-to-v1.md` 를 참조하세요.
(PR 5에서 작성 예정)

---

## 참고

- 구현 플랜: `docs/superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md`
- 설계 스펙: `docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md`
- 라이선스: MIT (v0.1과 동일)
