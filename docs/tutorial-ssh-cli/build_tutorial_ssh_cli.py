#!/usr/bin/env python3
"""Build script for the v1 SSH/CLI tutorial.

Produces docs/tutorial-ssh-cli/tutorial-ssh-cli.html.

Architecture context (v1):
- Single container: paperclip-hermes-codex (paperclipai + hermes dashboard + ttyd + codex CLI)
- Sidecar: tailscale (tailscale mode) or none (local mode)
- 4 named volumes: paperclip-data, hermes-data, codex-auth, tailscale-state
- Codex OAuth: codex login --device-auth (background, non-blocking) OR OPENAI_API_KEY
- Paperclip admin: auto-created via ADMIN_* env in entrypoint
- Expose: 3100 (Paperclip) / 9119 (Hermes Dashboard) / 4860 (ttyd terminal)

Sibling reference: docs/tutorial-hostinger-console/build_tutorial_hostinger_console.py
Spec: docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md §9.2
Plan: docs/superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md §9.2
"""
from __future__ import annotations

import importlib.util
import pathlib

BASE = pathlib.Path(__file__).resolve().parent
CAP  = BASE / "captures"
OUT  = BASE / "tutorial-ssh-cli.html"

# ---------------------------------------------------------------------------
# Reuse HEAD + render functions from the sibling v1 console tutorial
# ---------------------------------------------------------------------------
_SIBLING = BASE.parent / "tutorial-hostinger-console/build_tutorial_hostinger_console.py"
_spec = importlib.util.spec_from_file_location("_console_tutorial", _SIBLING)
_te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_te)

# Patch the title for this tutorial
HEAD = _te.HEAD.replace(
    "<title>Paperclip + Hermes + Codex — Hostinger 콘솔로 한 페이지에서 끝내기</title>",
    "<title>Paperclip + Hermes + Codex — SSH/CLI 직접 배포 가이드</title>",
)

# Import all reusable render helpers
esc           = _te.esc
mask          = _te.mask
MASK_PATTERNS = _te.MASK_PATTERNS
code_block    = _te.code_block
note_block    = _te.note_block
check_block   = _te.check_block
design_block  = _te.design_block
figure_block  = _te.figure_block
table         = _te.table
render_step   = _te.render_step

# ---------------------------------------------------------------------------
# Override figure_block to resolve assets relative to THIS tutorial's BASE
# ---------------------------------------------------------------------------

def figure_block(filename: str, caption: str) -> str:
    """Render a screenshot figure. Falls back to placeholder.svg if file missing."""
    asset_dir = BASE / "assets"
    capture_dir = BASE / "captures"
    target_asset = asset_dir / filename
    target_capture = capture_dir / filename
    if target_asset.exists():
        src = "assets/" + filename
        label_html = ""
    elif target_capture.exists():
        src = "captures/" + filename
        label_html = ""
    else:
        src = "assets/placeholder.svg"
        label_html = f'<span class="placeholder-tag">PLACEHOLDER · {esc(filename)}</span>'
    return f"""
    <figure class="screenshot">
      <img src="{src}" alt="{esc(caption)}" loading="lazy">
      {label_html}
      <figcaption>{esc(caption)}</figcaption>
    </figure>
    """


# ---------------------------------------------------------------------------
# SECTIONS — 10 steps, SSH/CLI 직접 배포, v1 single-container architecture
# ---------------------------------------------------------------------------

SECTIONS = [
    # ------------------------------------------------------------------
    # STEP 01 — VPS 구입 + SSH 키 등록
    # ------------------------------------------------------------------
    {
        "num": "01",
        "title": "VPS 구입 + SSH 키 등록",
        "lede": "Hostinger VPS를 구입하고 SSH 키를 등록해 비밀번호 없이 root 접속을 준비합니다.",
        "blocks": [
            note_block(
                "01-1. VPS 플랜 선택",
                "Hostinger hPanel → <strong>VPS</strong> → <strong>새 VPS 주문</strong>을 클릭합니다. "
                "OS는 <strong>Ubuntu 22.04 LTS</strong>를 선택하세요. "
                "이 스택의 메모리 footprint는 약 750 MB (Paperclip ~600 MB + Hermes ~100 MB + ttyd ~10 MB)이므로 "
                "<strong>KVM 2 (2 GB RAM)</strong> 이상 플랜을 권장합니다. "
                "구입 완료 후 hPanel에서 VPS IP 주소를 확인합니다.",
            ),
            code_block(
                "01-2. SSH 키 생성 (로컬 터미널)",
                """\
# 로컬 macOS / Linux 터미널에서 실행
ssh-keygen -t ed25519 -f ~/.ssh/hostinger -C "hostinger-vps"

# 공개키 내용 확인 (hPanel에 붙여넣을 값)
cat ~/.ssh/hostinger.pub""",
                "bash",
            ),
            note_block(
                "01-3. hPanel에서 SSH 키 등록",
                "hPanel → <strong>VPS</strong> → 서버 선택 → <strong>SSH Keys</strong> 탭 → <strong>Add SSH Key</strong>를 클릭합니다. "
                "위에서 출력한 공개키(<code>ssh-ed25519 AAAA...</code> 전체)를 붙여넣고 저장합니다. "
                "이미 비밀번호 로그인이 활성화된 서버는 이 단계에서 SSH 키를 추가하면 이후 키 인증만 사용할 수 있습니다.",
            ),
            code_block(
                "01-4. 첫 SSH 접속 확인",
                """\
# <VPS-IP>를 hPanel에서 확인한 실제 IP로 교체
ssh -i ~/.ssh/hostinger root@<VPS-IP>

# 접속 성공 시 출력 예시:
# Welcome to Ubuntu 22.04.4 LTS (GNU/Linux 5.15.0-101-generic x86_64)
# root@vps-abc:~#""",
                "bash",
            ),
            figure_block("01-vps-purchase.png", "Hostinger hPanel — VPS 구입 완료 및 IP 확인"),
            check_block(
                "01-5. 확인 기준",
                "SSH 키 인증으로 <code>root@&lt;VPS-IP&gt;</code> 접속이 성공합니다. "
                "비밀번호 입력 없이 바로 쉘 프롬프트가 나타나면 준비 완료입니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 02 — git clone + setup.sh
    # ------------------------------------------------------------------
    {
        "num": "02",
        "title": "git clone + setup.sh (MODE 선택)",
        "lede": "VPS에서 저장소를 클론하고 setup.sh를 실행해 .env를 자동 생성합니다. local 또는 tailscale 중 배포 모드를 선택합니다.",
        "blocks": [
            code_block(
                "02-1. Docker 설치 + 저장소 클론 (VPS 쉘에서)",
                """\
# Docker 설치 (Ubuntu 22.04 기준)
apt update && apt install -y git docker.io docker-compose-plugin

# systemd 서비스 등록 + 즉시 시작
systemctl enable --now docker

# 저장소 클론
git clone https://github.com/dandacompany/paperclip-hermes-codex-on-hostinger.git
cd paperclip-hermes-codex-on-hostinger""",
                "bash",
            ),
            table(
                rows=[
                    ("local", "127.0.0.1 포트 바인딩 — 로컬망·SSH 터널 접속", "VPN·방화벽 없이 간단 테스트"),
                    ("tailscale", "Tailscale 메시 + HTTPS 인증서 자동 발급", "인터넷 어디서나 .ts.net URL로 접속"),
                ],
                headers=("MODE", "동작 방식", "권장 시나리오"),
            ),
            code_block(
                "02-2. local 모드로 setup.sh 실행",
                """\
MODE=local \
  ADMIN_EMAIL=you@example.com \
  ADMIN_USERNAME=admin \
  ./setup.sh""",
                "bash",
            ),
            code_block(
                "02-3. tailscale 모드로 setup.sh 실행",
                """\
MODE=tailscale \
  TS_AUTHKEY=tskey-auth-<TS_AUTHKEY> \
  TS_HOSTNAME=paperclip \
  ADMIN_EMAIL=you@example.com \
  ADMIN_USERNAME=admin \
  ./setup.sh""",
                "bash",
            ),
            code_block(
                "02-4. .env 생성 확인",
                """\
# setup.sh 완료 후 자동 생성된 .env 확인
cat .env | head -10

# 예상 출력 (값은 자동 생성)
# MODE=tailscale
# ADMIN_USERNAME=admin
# ADMIN_EMAIL=you@example.com
# ADMIN_PASSWORD=<32자 자동 생성>
# TS_AUTHKEY=tskey-auth-<TS_AUTHKEY>
# TS_HOSTNAME=paperclip""",
                "bash",
            ),
            figure_block("02-setup-output.png", "setup.sh 실행 완료 — .env 파일 자동 생성"),
            check_block(
                "02-5. 확인 기준",
                "<code>.env</code> 파일이 생성되었고 <code>ADMIN_PASSWORD</code>가 32자 무작위 문자열로 채워져 있습니다. "
                "<code>cat .env</code> 출력에서 필수 변수 전부가 보이면 다음 단계로 진행합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 03 — .env 검토
    # ------------------------------------------------------------------
    {
        "num": "03",
        "title": ".env 검토 및 수정",
        "lede": "setup.sh가 생성한 .env를 확인하고 필요 시 추가 설정을 입력합니다.",
        "blocks": [
            code_block(
                "03-1. .env 전체 내용 확인",
                """\
cat .env""",
                "bash",
            ),
            table(
                rows=[
                    ("MODE", "필수", "local 또는 tailscale (setup.sh가 자동 기입)"),
                    ("ADMIN_USERNAME", "필수", "Paperclip + ttyd 로그인 ID"),
                    ("ADMIN_EMAIL", "필수", "Paperclip 관리자 이메일"),
                    ("ADMIN_PASSWORD", "자동 생성", "32자 무작위 — 안전한 곳에 보관"),
                    ("ADMIN_NAME", "선택", "표시 이름, 기본값 Owner"),
                    ("TS_AUTHKEY", "tailscale 전용", "Tailscale Auth Key"),
                    ("TS_HOSTNAME", "tailscale 전용", "Tailscale 노드 이름, 기본값 paperclip"),
                    ("OPENAI_API_KEY", "선택", "Codex OAuth 대신 API 키 인증 시 입력 (STEP 06 참조)"),
                ],
                headers=("변수", "필요 시점", "설명"),
            ),
            code_block(
                "03-2. ADMIN_NAME 수동 설정 (선택)",
                """\
# 표시 이름을 원하는 값으로 수정
# nano 또는 vi 사용
nano .env

# ADMIN_NAME= 줄을 찾아 수정
# ADMIN_NAME=단테""",
                "bash",
            ),
            check_block(
                "03-3. 확인 기준",
                "<code>ADMIN_PASSWORD</code>가 32자 자동 생성값으로 채워져 있고 "
                "<code>ADMIN_EMAIL</code>이 실제 이메일 주소로 기입되어 있습니다. "
                "<code>TS_AUTHKEY</code>는 tailscale 모드에서만 필요합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 04 — docker compose up -d + 상태 확인
    # ------------------------------------------------------------------
    {
        "num": "04",
        "title": "docker compose up -d + 상태 확인",
        "lede": "컨테이너 2개(또는 local 모드에서 1개)를 띄우고 health를 확인합니다.",
        "blocks": [
            code_block(
                "04-1. local 모드로 시작",
                """\
# local 모드 — paperclip-hermes-codex 단독
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d""",
                "bash",
            ),
            code_block(
                "04-2. tailscale 모드로 시작",
                """\
# tailscale 모드 — paperclip-hermes-codex + tailscale 사이드카
docker compose -f docker-compose.yml -f docker-compose.tailscale.yml up -d""",
                "bash",
            ),
            code_block(
                "04-3. 컨테이너 상태 확인",
                """\
docker compose ps

# 예상 출력 (tailscale 모드):
# NAME                                   STATUS
# paperclip-hermes-codex-on-hostinger-tailscale-1             running
# paperclip-hermes-codex-on-hostinger-paperclip-hermes-codex-1  running

# 예상 출력 (local 모드):
# NAME                                   STATUS
# paperclip-hermes-codex-on-hostinger-paperclip-hermes-codex-1  running""",
                "bash",
            ),
            code_block(
                "04-4. entrypoint 부트스트랩 로그 확인",
                """\
docker compose logs paperclip-hermes-codex --tail 30

# 정상 시 출력 순서:
# [entrypoint] Starting bootstrap...
# [entrypoint] Paperclip bootstrap complete
# [entrypoint] Hermes bootstrap complete
# [entrypoint] Starting supervisor...
# [supervisor] hermes dashboard started (pid XXXX)
# [supervisor] ttyd started (pid XXXX)""",
                "bash",
            ),
            figure_block("04-compose-up.png", "docker compose up -d — 컨테이너 시작 출력"),
            figure_block("04-logs.png", "docker compose logs — entrypoint 부트스트랩 로그"),
            check_block(
                "04-5. 확인 기준",
                "컨테이너가 <strong>running</strong> 상태이고 로그에 "
                "<code>[entrypoint] Starting supervisor...</code>가 출력됩니다. "
                "하나라도 <strong>exited</strong>이면 <code>docker compose logs</code>로 오류 줄을 확인합니다. "
                "부트스트랩 완료 시 Paperclip 관리자 계정이 자동 생성되고 추가 가입이 잠깁니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 05 — 첫 로그인 + Hermes Dashboard 검증
    # ------------------------------------------------------------------
    {
        "num": "05",
        "title": "첫 로그인 + Hermes Dashboard 검증",
        "lede": "3개 포트에 접속해 UI 동작을 확인합니다.",
        "blocks": [
            table(
                rows=[
                    ("Paperclip", "local: http://127.0.0.1:3100\ntailscale: https://<host>.ts.net:3100", "ADMIN_EMAIL + ADMIN_PASSWORD"),
                    ("Hermes Dashboard", "local: http://127.0.0.1:9119\ntailscale: https://<host>.ts.net:9119", "별도 인증 없음 (세션 자동 적용)"),
                    ("ttyd Terminal", "local: http://127.0.0.1:4860\ntailscale: https://<host>.ts.net:4860", "ADMIN_USERNAME + ADMIN_PASSWORD (basic-auth)"),
                ],
                headers=("서비스", "URL", "인증"),
            ),
            note_block(
                "05-1. local 모드 SSH 터널",
                "local 모드에서 로컬 PC 브라우저로 접속하려면 SSH 포트 포워딩을 사용합니다: "
                "<br><code>ssh -i ~/.ssh/hostinger -N -L 3100:127.0.0.1:3100 -L 9119:127.0.0.1:9119 -L 4860:127.0.0.1:4860 root@&lt;VPS-IP&gt;</code>"
                "<br>이후 <code>http://127.0.0.1:3100</code>에서 Paperclip에 접속합니다.",
            ),
            code_block(
                "05-2. Paperclip 접속 확인",
                """\
# 브라우저에서 열기
# local:     http://127.0.0.1:3100
# tailscale: https://paperclip.tail1234ab.ts.net:3100

# ADMIN_EMAIL + ADMIN_PASSWORD 로 로그인
# 로그인 성공 시 Agents / Tasks / Settings 사이드바가 보입니다""",
                "text",
            ),
            figure_block("05-paperclip-login.png", "Paperclip 로그인 페이지 — ADMIN_EMAIL + ADMIN_PASSWORD 입력"),
            figure_block("05-hermes-dashboard.png", "Hermes Dashboard — Sessions / Skills / API Keys 탭"),
            figure_block("05-ttyd.png", "ttyd Terminal — 브라우저 안 Hermes 쉘"),
            check_block(
                "05-3. 확인 기준",
                "3개 UI가 모두 정상 응답합니다. "
                "Paperclip은 워크스페이스 메인 화면, "
                "Hermes Dashboard는 Sessions 탭, "
                "ttyd는 터미널 프롬프트가 표시됩니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 06 — Codex OAuth
    # ------------------------------------------------------------------
    {
        "num": "06",
        "title": "Codex OAuth 부트스트랩",
        "lede": "컨테이너 로그에서 device URL을 찾아 브라우저로 1회 인증합니다. 이후 재인증은 불필요합니다.",
        "blocks": [
            code_block(
                "06-1. 로그에서 Codex OAuth URL 찾기",
                """\
docker compose logs paperclip-hermes-codex | grep -i "codex"

# 예상 출력:
# [codex-oauth] No auth.json found — starting device auth
# [codex-oauth] Open this URL to authenticate:
# [codex-oauth] https://auth.openai.com/device?user_code=XXXX-XXXX
# [codex-oauth] Code: XXXX-XXXX (expires in 15 minutes)""",
                "bash",
            ),
            note_block(
                "06-2. device URL 형식",
                "URL은 <code>https://auth.openai.com/device?user_code=XXXX-XXXX</code> 형식입니다. "
                "로그에서 해당 줄을 복사해 브라우저에 붙여넣습니다. "
                "코드 만료 시간(15분) 안에 인증을 완료해야 합니다. "
                "시간이 지났다면 컨테이너를 재시작하면 새 URL이 발급됩니다: "
                "<code>docker compose restart paperclip-hermes-codex</code>",
            ),
            code_block(
                "06-3. 브라우저 인증 절차",
                """\
# 1. 로그에서 복사한 URL을 새 탭에서 엽니다
#    예: https://auth.openai.com/device?user_code=XXXX-XXXX

# 2. ChatGPT / OpenAI 계정으로 로그인 후 "Allow" 클릭

# 3. 인증 완료 후 로그에서 확인
docker compose logs paperclip-hermes-codex | grep "OAuth completed"
# 예상 출력:
# [codex-oauth] Codex OAuth completed — auth.json saved""",
                "bash",
            ),
            note_block(
                "06-4. API 키 fallback",
                "OAuth 대신 API 키를 사용하려면 <code>.env</code>에 <code>OPENAI_API_KEY=sk-...</code>를 추가하고 "
                "컨테이너를 재시작합니다. "
                "Codex CLI 0.122+ 버전은 이 값을 자동으로 <code>auth.json</code> 형식으로 변환합니다. "
                "OAuth와 API 키 중 하나만 있으면 충분합니다.",
            ),
            code_block(
                "06-5. auth.json 생성 확인",
                """\
docker exec paperclip-hermes-codex-on-hostinger-paperclip-hermes-codex-1 \
  ls -la /home/node/.codex/

# 예상 출력:
# -rw------- 1 node node 312 Jan 01 12:00 auth.json""",
                "bash",
            ),
            figure_block("06-codex-log.png", "docker compose logs — Codex OAuth URL 출력"),
            figure_block("06-codex-browser.png", "ChatGPT 디바이스 인증 페이지 — Allow 클릭"),
            check_block(
                "06-6. 확인 기준",
                "로그에 <strong>[codex-oauth] Codex OAuth completed</strong>가 출력됩니다. "
                "<code>/home/node/.codex/auth.json</code>이 생성되었고 크기가 0 이상입니다. "
                "이 파일은 <code>codex-auth</code> named volume에 영구 저장되므로 "
                "컨테이너 재시작 후에도 재인증이 필요 없습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 07 — 첫 CEO 에이전트 + Test now
    # ------------------------------------------------------------------
    {
        "num": "07",
        "title": "첫 CEO 에이전트 생성 + Test now",
        "lede": "Paperclip UI에서 Hermes Agent 어댑터를 사용하는 CEO 에이전트를 만들고 어댑터 환경을 검증합니다.",
        "blocks": [
            code_block(
                "07-1. 에이전트 생성 절차",
                """\
# Paperclip UI (http://127.0.0.1:3100 또는 https://<fqdn>:3100)
# 1. 왼쪽 사이드바 → Agents → + New Agent 클릭
# 2. Name: CEO (또는 원하는 이름)
# 3. Adapter type: "Hermes Agent" 선택
# 4. Hermes URL: http://localhost:9119  (컨테이너 내부 주소)
# 5. Role / Persona: 에이전트 역할 입력 (예: "You are a CEO agent...")
# 6. Save 클릭""",
                "bash",
            ),
            note_block(
                "07-2. Hermes Agent 어댑터가 동작하는 이유",
                "v1 단일 컨테이너는 <code>hermes</code> 바이너리를 <code>/opt/hermes/.venv/bin/</code>에 포함합니다. "
                "Paperclip의 어댑터 환경 체크(<em>Adapter env check</em>)는 같은 컨테이너 PATH에서 바이너리를 즉시 발견하므로 "
                "추가 설치 없이 통과됩니다. "
                "<code>PATH 에러</code>가 발생하면 컨테이너 로그에서 <code>[supervisor] hermes dashboard</code>가 "
                "정상 시작했는지 확인합니다.",
            ),
            code_block(
                "07-3. Test now 실행",
                """\
# 에이전트 상세 페이지 → "Test now" 버튼 클릭
# 성공 시 표시:
Adapter env check: passed""",
                "text",
            ),
            figure_block("07-create-agent.png", "Paperclip — 에이전트 생성 폼, Hermes Agent 어댑터 선택"),
            figure_block("07-test-passed.png", "Paperclip — Test now 결과: Adapter env check: passed"),
            check_block(
                "07-4. 확인 기준",
                "Test now 클릭 후 <strong>Adapter env check: passed</strong> 메시지가 표시됩니다. "
                "오류가 나면 <code>docker compose logs paperclip-hermes-codex | grep supervisor</code>에서 "
                "Hermes Dashboard 프로세스 상태를 확인합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 08 — 첫 Task 실행 + 체인 검증
    # ------------------------------------------------------------------
    {
        "num": "08",
        "title": "첫 Task 실행 + 체인 검증",
        "lede": "간단한 Task를 실행해 Paperclip → Hermes → Codex → OpenAI 전체 체인이 연결되었는지 확인합니다.",
        "blocks": [
            code_block(
                "08-1. Task 생성",
                """\
# Paperclip UI → Tasks → + New Task
# Title: Hello Chain
# Description: Respond with hello
# Agent: CEO (STEP 07에서 생성한 에이전트)
# Run 클릭""",
                "bash",
            ),
            note_block(
                "08-2. 체인 흐름",
                "Paperclip이 태스크를 Hermes Agent에 전달합니다 → "
                "Hermes는 <code>codex run</code>으로 Codex CLI를 spawn합니다 → "
                "Codex CLI는 <code>auth.json</code> 토큰으로 OpenAI API를 호출합니다 → "
                "결과가 역순으로 전달되어 Paperclip Task 상세 페이지에 반환됩니다.",
            ),
            code_block(
                "08-3. 실시간 로그로 체인 추적",
                """\
# 별도 터미널에서 실행 중인 로그를 스트리밍
docker compose logs paperclip-hermes-codex -f --tail 50

# 또는 컨테이너 안에서 Hermes 로그 직접 확인
docker exec -it paperclip-hermes-codex-on-hostinger-paperclip-hermes-codex-1 \
  tail -f /home/node/.hermes/logs/*.log""",
                "bash",
            ),
            figure_block("08-task-running.png", "Paperclip — Task 실행 중 상태"),
            figure_block("08-task-result.png", "Paperclip — Task 완료 및 결과 반환"),
            check_block(
                "08-4. 확인 기준",
                "Task 상세 페이지에 에이전트 응답이 표시됩니다. "
                "Status가 <strong>completed</strong>이면 전체 체인 검증이 완료됩니다. "
                "Status가 <strong>failed</strong>이면 STEP 06 Codex OAuth가 완료되었는지 다시 확인합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 09 — 업데이트
    # ------------------------------------------------------------------
    {
        "num": "09",
        "title": "업데이트 (compose pull + up -d)",
        "lede": "새 이미지를 pull하고 컨테이너를 재시작합니다. 데이터는 named volume에 보존됩니다.",
        "blocks": [
            code_block(
                "09-1. 최신 이미지 다운로드",
                """\
# VPS 쉘에서 실행 (저장소 디렉터리 안)
cd paperclip-hermes-codex-on-hostinger
docker compose pull

# 예상 출력:
# [+] Pulling 2/2
# paperclip-hermes-codex Pulled
# tailscale Pulled""",
                "bash",
            ),
            code_block(
                "09-2. 변경된 컨테이너만 재생성",
                """\
# local 모드
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# tailscale 모드
docker compose -f docker-compose.yml -f docker-compose.tailscale.yml up -d

# 예상 출력:
# [+] Running 2/2
#  Container paperclip-hermes-codex-on-hostinger-tailscale-1             Started
#  Container paperclip-hermes-codex-on-hostinger-paperclip-hermes-codex-1  Started""",
                "bash",
            ),
            code_block(
                "09-3. volume 보존 확인",
                """\
docker volume ls | grep paperclip-hermes-codex

# 예상 출력 (4개 volume 모두 유지):
# local   paperclip-hermes-codex-on-hostinger_codex-auth
# local   paperclip-hermes-codex-on-hostinger_hermes-data
# local   paperclip-hermes-codex-on-hostinger_paperclip-data
# local   paperclip-hermes-codex-on-hostinger_tailscale-state""",
                "bash",
            ),
            note_block(
                "09-4. GHA nightly 빌드",
                "GitHub Actions가 매일 KST 12:17에 최신 소스 이미지를 pull해 "
                "<code>ghcr.io/dandacompany/paperclip-hermes-codex:latest</code>를 재빌드합니다. "
                "특정 버전으로 고정하려면 <code>.env</code>에 "
                "<code>IMAGE_TAG=ghcr.io/dandacompany/paperclip-hermes-codex:&lt;sha&gt;</code>를 추가하고 "
                "compose 파일의 <code>image:</code> 필드를 참조하도록 수정합니다.",
            ),
            check_block(
                "09-5. 확인 기준",
                "재시작 후 Paperclip UI 로그인 없이 기존 Agents와 Tasks가 그대로 보입니다. "
                "Codex OAuth를 다시 하지 않아도 Task 실행이 정상 동작하면 업데이트 완료입니다. "
                "세션 쿠키와 Codex <code>auth.json</code> 모두 named volume에 영구 보존됩니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 10 — 백업/복원
    # ------------------------------------------------------------------
    {
        "num": "10",
        "title": "백업 / 복원 (volume tarball 4종)",
        "lede": "모든 데이터를 volume tarball로 백업하고 새 서버나 재설치 환경에서 복원합니다.",
        "blocks": [
            code_block(
                "10-1. 4개 volume 백업",
                """\
mkdir -p backups

# paperclip-data (워크스페이스 DB + 설정)
docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_paperclip-data:/data \
  -v $PWD/backups:/out \
  alpine tar czf /out/paperclip-data-$(date +%Y%m%d).tgz -C /data .

# hermes-data (세션, 스킬, API 키)
docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_hermes-data:/data \
  -v $PWD/backups:/out \
  alpine tar czf /out/hermes-data-$(date +%Y%m%d).tgz -C /data .

# codex-auth (Codex OAuth 토큰)
docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_codex-auth:/data \
  -v $PWD/backups:/out \
  alpine tar czf /out/codex-auth-$(date +%Y%m%d).tgz -C /data .

# tailscale-state (Tailscale 노드 ID + 인증서)
docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_tailscale-state:/data \
  -v $PWD/backups:/out \
  alpine tar czf /out/tailscale-state-$(date +%Y%m%d).tgz -C /data .

ls -lh backups/""",
                "bash",
            ),
            code_block(
                "10-2. volume 복원",
                """\
# 복원할 VPS에서 저장소 클론 + setup.sh 완료 후
# 컨테이너 정지 (volume 잠금 해제)
docker compose down

# 4개 volume 각각 복원 (날짜를 실제 파일명으로 교체)
docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_paperclip-data:/data \
  -v $PWD/backups:/in \
  alpine tar xzf /in/paperclip-data-20260101.tgz -C /data

docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_hermes-data:/data \
  -v $PWD/backups:/in \
  alpine tar xzf /in/hermes-data-20260101.tgz -C /data

docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_codex-auth:/data \
  -v $PWD/backups:/in \
  alpine tar xzf /in/codex-auth-20260101.tgz -C /data

docker run --rm \
  -v paperclip-hermes-codex-on-hostinger_tailscale-state:/data \
  -v $PWD/backups:/in \
  alpine tar xzf /in/tailscale-state-20260101.tgz -C /data

# 컨테이너 재시작
docker compose -f docker-compose.yml -f docker-compose.tailscale.yml up -d""",
                "bash",
            ),
            note_block(
                "10-3. 4개 volume의 역할",
                "<strong>paperclip-data</strong>: Paperclip 워크스페이스 데이터 (에이전트, 태스크, 설정) "
                "| <strong>hermes-data</strong>: Hermes 세션, 스킬 패키지, API 키 "
                "| <strong>codex-auth</strong>: Codex OAuth 토큰 (<code>auth.json</code>) "
                "| <strong>tailscale-state</strong>: Tailscale 노드 ID + MagicDNS 인증서. "
                "4개 모두 백업해야 완전 복원이 가능합니다. "
                "tailscale-state를 복원하면 동일 Tailscale 노드 ID로 재연결되어 FQDN이 유지됩니다.",
            ),
            check_block(
                "10-4. 확인 기준",
                "백업 후 <code>docker compose down -v</code>로 volume을 완전 삭제하고, "
                "<code>up -d</code> + restore 순서로 복원한 뒤 Paperclip 로그인이 가능하면 "
                "백업 완전성이 검증됩니다. "
                "Codex OAuth를 다시 하지 않고 Task 실행이 성공하면 <code>codex-auth</code> volume 복원도 정상입니다.",
            ),
        ],
    },
]


# ---------------------------------------------------------------------------
# Body builder — hero meta-grid + steps + footer
# ---------------------------------------------------------------------------

def body() -> str:
    rendered = "\n".join(render_step(section) for section in SECTIONS)
    return f"""
<body>
  <header class="hero">
    <div class="hero-inner">
      <span class="eyebrow">SSH/CLI · Paperclip × Hermes × Codex — v1</span>
      <h1>Paperclip + Hermes + Codex — SSH/CLI 직접 배포 가이드</h1>
      <p>VPS에 SSH로 접속해 git clone + setup.sh + docker compose 10단계로 배포합니다. local 또는 tailscale 모드를 선택하고 Codex OAuth 1회 인증으로 영구 사용합니다.</p>
      <dl class="meta-grid">
        <div><dt>대상</dt><dd>SSH 접근 가능한 사용자</dd></div>
        <div><dt>모드</dt><dd>local | tailscale</dd></div>
        <div><dt>컨테이너</dt><dd>2개 (paperclip-hermes-codex + tailscale)</dd></div>
        <div><dt>노출 포트</dt><dd>3100 / 9119 / 4860</dd></div>
        <div><dt>업데이트</dt><dd>docker compose pull &amp;&amp; up -d</dd></div>
        <div><dt>백업</dt><dd>volume tarball 4종</dd></div>
      </dl>
    </div>
  </header>
  <main class="container">
    {rendered}
  </main>
  <footer>
    <p>저장소 · <a href="https://github.com/dandacompany/paperclip-hermes-codex-on-hostinger">github.com/dandacompany/paperclip-hermes-codex-on-hostinger</a></p>
    <p>Hostinger 콘솔 기반 배포 · <a href="../tutorial-hostinger-console/tutorial-hostinger-console.html">docs/tutorial-hostinger-console/</a></p>
    <p>마이그레이션 가이드 · <a href="../MIGRATION-v0.1-to-v1.md">docs/MIGRATION-v0.1-to-v1.md</a></p>
    <p>아키텍처 스펙 · <a href="../superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md">docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md</a></p>
    <p>구현 플랜 · <a href="../superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md">docs/superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md</a></p>
  </footer>
</body>
</html>
"""


def main() -> None:
    html_text = HEAD + body()
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    OUT.write_text(html_text, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
