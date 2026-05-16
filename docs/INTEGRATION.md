# Integration: Hermes ↔ Paperclip

두 시스템을 같은 Docker 브리지 네트워크에 두는 사이드카 구성의 진짜 가치는 **호스트 IP·외부 토큰 교환 없이 서로 HTTP로 직접 통신**할 수 있다는 점입니다.

## 두 시스템의 역할 분담

| 시스템 | 정체성 | 핵심 책임 |
|---|---|---|
| **Paperclip** | Control plane / 작업 관리 | 작업·라우틴·승인·코멘트 워크플로. heartbeat로 에이전트 깨움 |
| **Hermes** | Agent runtime | LLM 호출, 메시징 게이트웨이, 스킬 실행, 메모리 |

즉 Paperclip은 "**어떤 일을 누가 언제 할지**"를 결정하고, Hermes는 "**그 일을 실제로 수행**"합니다. 비유하자면 Paperclip = PM·이슈 트래커, Hermes = 개발자.

## 사이드카 네트워크 토폴로지

```
   ┌──── Docker bridge: hermes-paperclip_net ────┐
   │                                              │
   │   hermes-dashboard:9119                      │
   │   hermes-tui:4860                            │
   │   hermes-gateway (cron+messaging, opt-in)    │
   │                                              │
   │   paperclip:3100                             │
   │                                              │
   └──────────────────────────────────────────────┘

서비스 명으로 직접 도달:
- Hermes → http://paperclip:3100/api/...
- Paperclip → http://hermes-dashboard:9119/...
```

호스트 IP·외부 도메인·외부 토큰 발급 절차 모두 불필요. 컨테이너 안에서 `docker exec`로 확인:

```bash
docker compose exec hermes-dashboard curl -sS http://paperclip:3100/api/health
docker compose exec paperclip curl -sS http://hermes-dashboard:9119/
```

## Heartbeat — Paperclip이 Hermes를 깨우는 메커니즘

Paperclip은 작업 트리거 시점에 **에이전트 어댑터**를 호출합니다. 어댑터는 환경 변수에 short-lived JWT(`PAPERCLIP_API_KEY`)와 작업 컨텍스트를 주입한 채 에이전트 프로세스를 spawn:

```
PAPERCLIP_API_URL=http://paperclip:3100/api
PAPERCLIP_API_KEY=<short-lived JWT>
PAPERCLIP_AGENT_ID=<agent uuid>
PAPERCLIP_COMPANY_ID=<company uuid>
PAPERCLIP_RUN_ID=<run uuid>
PAPERCLIP_TASK_ID=<task uuid>             # 트리거 작업
PAPERCLIP_WAKE_REASON=<comment|cron|...>  # 깬 이유
```

에이전트는 짧은 실행 윈도우(heartbeat) 안에 일을 끝내고 종료. 컨텍스트는 `PAPERCLIP_TASK_ID`로 작업 다시 fetch.

## 일반적 연동 흐름

### 시나리오 A — Paperclip이 Hermes에게 작업 위임

1. 사용자가 Paperclip 콘솔에서 작업 등록 (`/paperclip` 도메인)
2. 작업의 어시그니가 Hermes 에이전트 (사전 등록됨)
3. Paperclip이 heartbeat → Hermes 컨테이너 안에서 짧은 process spawn
4. Hermes가 LLM 호출·스킬 실행·결과 생성
5. Hermes가 `POST http://paperclip:3100/api/issues/<task_id>/comments` 로 결과 코멘트
6. 사용자가 Paperclip 콘솔에서 결과 확인

### 시나리오 B — Hermes가 Paperclip에 작업 등록

1. 사용자가 Slack/Telegram으로 Hermes에 "이걸 추적 작업으로 만들어줘"
2. Hermes 게이트웨이가 사용자 의도 파싱
3. Hermes가 `POST http://paperclip:3100/api/issues` 로 신규 작업 생성
4. 다른 팀원에게 어시그닝 (Paperclip의 사용자·에이전트 목록 활용)
5. Paperclip이 어시그니에게 알림 (이메일·Slack 등 — Paperclip 자체 통합 사용)

### 시나리오 C — Hermes 게이트웨이가 Paperclip 라우틴으로 결과 푸시

1. Hermes의 `cron` 라우틴이 매일 09:00에 일일 요약 작성
2. 결과를 `POST http://paperclip:3100/api/issues/<daily_summary_id>/comments` 로 push
3. Paperclip이 작업 단위로 결과 누적 → 트렌드 분석 등

## Hermes 안에서 Paperclip API 호출하기

Hermes의 skill 또는 스크립트 안에서:

```python
import os, requests

PAPERCLIP_URL = os.environ.get("PAPERCLIP_API_URL", "http://paperclip:3100/api")
PAPERCLIP_KEY = os.environ["PAPERCLIP_API_KEY"]    # heartbeat 시 자동 주입

def post_comment(task_id: str, body: str):
    return requests.post(
        f"{PAPERCLIP_URL}/issues/{task_id}/comments",
        headers={
            "Authorization": f"Bearer {PAPERCLIP_KEY}",
            "X-Paperclip-Run-Id": os.environ["PAPERCLIP_RUN_ID"],
        },
        json={"body": body},
    )
```

Heartbeat 외 경로(예: 사용자 명령으로 Hermes가 직접 호출)에선 `PAPERCLIP_API_KEY`가 없으므로 **장기 API 토큰을 별도 발급**해야 합니다. Paperclip 콘솔 → Settings → API Tokens.

## Paperclip 안에서 Hermes 호출하기

Paperclip 어댑터 설정에서 Hermes를 "external agent"로 등록. Adapter type 중 HTTP webhook 어댑터를 쓰면:

```
Adapter URL: http://hermes-dashboard:9119/api/agents/run
Auth: Bearer <Hermes 토큰>    (Hermes 콘솔에서 발급)
```

Paperclip이 heartbeat 트리거 시 위 URL로 작업 컨텍스트 POST → Hermes가 받아 처리.

## 데이터 분리 — 두 볼륨, 한 의도

| 볼륨 | 내용 | UID |
|---|---|---|
| `hermes-data` | Hermes config, 세션, 메모리, 스킬, 로그 | 10000 |
| `paperclip-data` | Paperclip DB(SQLite), 자격, 작업 데이터 | 1000 |

같은 호스트의 별개 named volume. 한 쪽 재설치·롤백이 다른 쪽 영향 없음.

백업 권장:

```bash
# Hermes 데이터
docker run --rm -v hermes-paperclip_hermes-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/hermes-data-$(date +%Y%m%d).tar.gz -C /data .

# Paperclip 데이터
docker run --rm -v hermes-paperclip_paperclip-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/paperclip-data-$(date +%Y%m%d).tar.gz -C /data .
```

복원은 역방향:

```bash
docker run --rm -v hermes-paperclip_hermes-data:/data -v "$PWD":/backup alpine \
  tar xzf /backup/hermes-data-20260516.tar.gz -C /data
```

## 한 인스턴스에서 여러 워크플로 운영

같은 Hermes + Paperclip 한 쌍이 동시에 여러 워크플로 실행 가능:

- Paperclip의 **워크스페이스**나 **라벨**로 작업 분류
- Hermes의 **프로필**로 다른 페르소나 운영 (옵션 — 본 OSS는 default 프로필 1개로 시작)

규모가 더 커지면 (예: 회사 단위 다중 팀), 인스턴스를 분리하는 게 자연스럽습니다 — 각 팀이 자기 compose 디렉터리에서 같은 install.sh 한 줄로 띄움. 각 인스턴스가 독립 tailnet 또는 cloudflared 튜널.

## 트러블슈팅

### Hermes가 `paperclip:3100`에 못 닿음

```bash
docker compose exec hermes-dashboard sh -c 'curl -v http://paperclip:3100/api/health' 2>&1 | tail -10
```

- DNS resolution 실패 → 같은 compose `default` 네트워크 안에 있는지 `docker network inspect <project>_net` 확인. 두 서비스 모두 보이는지.
- Connection refused → paperclip 컨테이너 죽음. `docker compose logs paperclip` 확인.

### Paperclip의 `PAPERCLIP_API_KEY`가 만료됨

Heartbeat 단위로 짧은 만료(보통 분 단위)이므로 정상 행동. 다음 heartbeat에 새 키 발급. 만약 외부에서 장시간 보관하고 싶으면 Paperclip 콘솔에서 long-lived token 별도 발급.

### 두 시스템의 사용자/팀 모델 정렬

Paperclip은 자체 사용자·역할 모델, Hermes는 SOUL.md·skills 단위로 페르소나. 직접 매핑은 안 됨 — 각자 운영하고, 한 사람이 양쪽 콘솔에 같은 이메일로 등록되는 패턴 권장.
