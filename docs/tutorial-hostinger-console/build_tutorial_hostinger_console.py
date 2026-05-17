#!/usr/bin/env python3
"""Build script for the v1 Hostinger Console tutorial.

Produces docs/tutorial-hostinger-console/tutorial-hostinger-console.html.

Architecture context (v1):
- Single container: paperclip-hermes-codex (paperclipai + hermes dashboard + ttyd + codex CLI)
- Sidecar: tailscale
- 4 named volumes: paperclip-data, hermes-data, codex-auth, tailscale-state
- Codex OAuth: codex login --device-auth  (background, non-blocking)
- Paperclip admin: auto-created via ADMIN_* env in entrypoint
- Expose: 3100 (Paperclip) / 9119 (Hermes Dashboard) / 4860 (ttyd terminal)

Sibling reference: v0.1-sidecar tag  →  git checkout v0.1-sidecar
Migration guide:   docs/MIGRATION-v0.1-to-v1.md
"""
from __future__ import annotations

import html
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parent
OUT = BASE / "tutorial-hostinger-console.html"

# ---------------------------------------------------------------------------
# Secret masking — extend for v1 secrets
# ---------------------------------------------------------------------------
MASK_PATTERNS = [
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"), "xoxb-<SLACK_TOKEN>"),
    (re.compile(r"xapp-[A-Za-z0-9-]{20,}"), "xapp-<SLACK_APP_TOKEN>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-<OPENAI_API_KEY>"),
    (re.compile(r"tskey-auth-[A-Za-z0-9-]{20,}"), "tskey-auth-<TS_AUTHKEY>"),
    # Codex auth.json bearer tokens
    (re.compile(r'"token"\s*:\s*"[A-Za-z0-9._-]{20,}"'), '"token": "<CODEX_TOKEN>"'),
    # Generic bearer tokens in curl headers
    (re.compile(r"Bearer [A-Za-z0-9._-]{20,}"), "Bearer <TOKEN>"),
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def mask(text: str) -> str:
    for pattern, repl in MASK_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------

def code_block(label: str, text: str, lang: str = "") -> str:
    return f"""
    <div class="code-block">
      <div class="code-header">
        <span class="dots"><i></i><i></i><i></i></span>
        <span>{esc(label)}</span>
      </div>
      <pre><code class="language-{esc(lang)}">{esc(mask(text.strip()))}</code></pre>
    </div>
    """


def note_block(label: str, text: str) -> str:
    return f"""
    <aside class="note-block">
      <div class="block-label">{esc(label)}</div>
      <p>{text}</p>
    </aside>
    """


def check_block(label: str, text: str) -> str:
    """Green-accented verification/success block."""
    return f"""
    <aside class="check-block">
      <div class="block-label">{esc(label)}</div>
      <p>{text}</p>
    </aside>
    """


def design_block(label: str, goal: str, principles: list[str], components: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f"<li><span>{idx:02d}</span><p>{esc(item)}</p></li>"
        for idx, item in enumerate(principles, 1)
    )
    cards = "\n".join(
        f"<article><strong>{esc(name)}</strong><p>{esc(desc)}</p></article>"
        for name, desc in components
    )
    return f"""
    <section class="design-block">
      <div class="block-label">{esc(label)}</div>
      <p class="goal">{esc(goal)}</p>
      <ol class="principles">{items}</ol>
      <div class="component-grid">{cards}</div>
    </section>
    """


def figure_block(filename: str, caption: str) -> str:
    """Render a screenshot figure. Falls back to placeholder.svg if file missing."""
    asset_dir = BASE / "assets"
    target = asset_dir / filename
    src = filename if target.exists() else "assets/placeholder.svg"
    label = filename if not target.exists() else ""
    label_html = (
        f'<span class="placeholder-tag">PLACEHOLDER · {esc(label)}</span>'
        if label
        else ""
    )
    return f"""
    <figure class="screenshot">
      <img src="{'assets/' + esc(filename) if target.exists() else 'assets/placeholder.svg'}" alt="{esc(caption)}" loading="lazy">
      {label_html}
      <figcaption>{esc(caption)}</figcaption>
    </figure>
    """


def table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> str:
    body_html = "\n".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
        for row in rows
    )
    head_html = "".join(f"<th>{esc(h)}</th>" for h in headers)
    return f"""
    <table>
      <thead><tr>{head_html}</tr></thead>
      <tbody>{body_html}</tbody>
    </table>
    """


# ---------------------------------------------------------------------------
# SECTIONS — 11 steps, v1 single-container architecture
# ---------------------------------------------------------------------------

SECTIONS = [
    # ------------------------------------------------------------------
    # STEP 01
    # ------------------------------------------------------------------
    {
        "num": "01",
        "title": "hPanel → VPS → Docker Manager",
        "lede": "Hostinger hPanel 왼쪽 사이드바에서 VPS 항목을 열고 Docker Manager 탭으로 이동합니다.",
        "blocks": [
            design_block(
                "01-1. 이 스택이 하는 일",
                "Paperclip + Hermes + Codex CLI가 단일 컨테이너 안에서 동작합니다. SSH 없이 hPanel 콘솔만으로 배포·운영·업데이트가 완결됩니다.",
                [
                    "Paperclip (port 3100) — 에이전트 오케스트레이터 + Web UI. 태스크를 받아 Hermes 워커에 전달합니다.",
                    "Hermes Dashboard (port 9119) — 세션·스킬·API 키 관리 SPA. 브라우저에서 직접 접근합니다.",
                    "ttyd Terminal (port 4860) — 브라우저 안 Hermes 쉘. 별도 SSH 없이 CLI를 사용할 수 있습니다.",
                    "Codex CLI — Hermes가 태스크별로 spawn하는 LLM 백엔드. OpenAI API를 직접 호출합니다.",
                ],
                [
                    ("paperclip-hermes-codex", "Paperclip + Hermes + Codex가 하나로 묶인 메인 컨테이너"),
                    ("tailscale", "Tailscale 메시 사이드카 — .ts.net FQDN + HTTPS 자동 인증서"),
                    ("4 named volumes", "paperclip-data / hermes-data / codex-auth / tailscale-state — 이미지 업데이트해도 영구 보존"),
                ],
            ),
            table(
                rows=[
                    ("컨테이너", "2개", "paperclip-hermes-codex + tailscale"),
                    ("노출 포트", "3100 / 9119 / 4860", "Tailscale HTTPS로 외부 노출"),
                    ("인증", "ADMIN_* env 자동 + Codex OAuth 1회", "첫 부팅 시 entrypoint가 자동 처리"),
                    ("업데이트", "콘솔 Update 버튼 1클릭", "docker compose pull + up -d"),
                    ("데이터 보존", "named volume 4개", "컨테이너 재생성해도 유지"),
                    ("권장 RAM", "2 GB 이상", "Hostinger KVM 2 플랜 이상"),
                ],
                headers=("항목", "값", "설명"),
            ),
            figure_block("01-hpanel-vps.png", "hPanel 왼쪽 사이드바 → VPS → Docker Manager 탭"),
            note_block(
                "01-2. 콘솔 접근 경로",
                "hPanel 로그인 → 왼쪽 사이드바 <strong>VPS</strong> 클릭 → 서버 선택 → 상단 탭 중 <strong>Docker Manager</strong>를 클릭합니다. "
                "Docker Manager가 보이지 않으면 VPS 플랜이 Docker 지원 여부를 확인하세요.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 02
    # ------------------------------------------------------------------
    {
        "num": "02",
        "title": "URL에서 컴포즈 가져오기",
        "lede": "Docker Manager의 \"URL에서 컴포즈 가져오기\" 입력란에 아래 URL을 붙여넣고 가져오기를 클릭합니다.",
        "blocks": [
            code_block(
                "02-1. Compose URL",
                "https://raw.githubusercontent.com/dandacompany/paperclip-hermes-codex-on-hostinger/main/docker-compose.console.yml",
                "text",
            ),
            figure_block("02-docker-manager-url-import.png", "Docker Manager — URL에서 컴포즈 가져오기 입력란에 URL 붙여넣기"),
            note_block(
                "02-2. console.yml이 하는 일",
                "<code>docker-compose.console.yml</code>은 단독 실행 가능한 self-contained 파일입니다. "
                "메인 컨테이너(<code>paperclip-hermes-codex</code>)와 Tailscale 사이드카를 함께 정의하며, "
                "부팅 시 GitHub Raw에서 <code>tailscale/serve.json</code>을 자동으로 내려받아 3100·9119·4860 포트를 HTTPS로 라우팅합니다. "
                "SSH나 별도 파일 업로드 없이 이 URL 한 줄로 전체 스택이 올라옵니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 03
    # ------------------------------------------------------------------
    {
        "num": "03",
        "title": "환경변수 입력",
        "lede": "가져온 컴포즈 아래 환경변수 폼에 아래 값을 입력합니다. OPENAI_API_KEY는 지금 비워두어도 됩니다.",
        "blocks": [
            table(
                rows=[
                    ("ADMIN_USERNAME", "필수", "Paperclip + Hermes TUI 로그인 ID (예: admin)"),
                    ("ADMIN_EMAIL", "필수", "Paperclip 관리자 이메일"),
                    ("ADMIN_PASSWORD", "필수", "Paperclip + Hermes TUI 비밀번호 (8자 이상 권장)"),
                    ("ADMIN_NAME", "선택", "표시 이름, 기본값 Owner"),
                    ("TS_AUTHKEY", "필수", "Tailscale Auth Key — 아래 발급 방법 참고"),
                    ("TS_HOSTNAME", "선택", "Tailscale 노드 이름, 기본값 paperclip"),
                    ("PAPERCLIP_PUBLIC_URL", "나중에 입력", "STEP 05에서 Tailscale FQDN 확인 후 입력"),
                    ("OPENAI_API_KEY", "선택", "Codex OAuth 대신 API 키로 인증할 때 입력. 지금은 비워두기"),
                ],
                headers=("변수", "필요 시점", "설명"),
            ),
            code_block(
                "03-2. Tailscale Auth Key 발급",
                """\
# 브라우저에서 아래 URL 열기
https://login.tailscale.com/admin/settings/keys

# "Generate auth key" 클릭 후:
#   - Reusable: 체크
#   - Expiry: 90일 이상
#   - Tags: 선택 사항
# 발급된 tskey-auth-... 값을 TS_AUTHKEY 필드에 붙여넣습니다.""",
                "bash",
            ),
            figure_block("03-env-vars-form.png", "환경변수 폼 입력 — ADMIN_*, TS_AUTHKEY 입력, OPENAI_API_KEY는 빈칸"),
            note_block(
                "03-3. OPENAI_API_KEY를 지금 비워두는 이유",
                "STEP 08에서 Codex OAuth 1회 브라우저 인증을 완료하면 토큰이 <code>codex-auth</code> named volume에 영구 저장됩니다. "
                "이후 컨테이너를 재시작하거나 이미지를 업데이트해도 재인증이 필요 없습니다. "
                "API 키 방식을 선호한다면 <code>OPENAI_API_KEY</code>를 지금 입력해도 되며, "
                "Codex CLI 0.122+ 이상은 이 값을 자동으로 <code>auth.json</code>으로 변환합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 04
    # ------------------------------------------------------------------
    {
        "num": "04",
        "title": "배포 + 컨테이너 2개 상태 확인",
        "lede": "\"배포\" 버튼을 클릭합니다. Docker Manager가 이미지를 pull하고 두 컨테이너를 순서대로 시작합니다.",
        "blocks": [
            note_block(
                "04-1. 배포 순서",
                "Tailscale 사이드카가 먼저 healthy 상태가 된 뒤 <code>paperclip-hermes-codex</code> 컨테이너가 시작됩니다 "
                "(<code>depends_on: tailscale: condition: service_healthy</code>). "
                "전체 배포는 이미지 크기에 따라 1~3분이 소요됩니다.",
            ),
            code_block(
                "04-2. 정상 시작 시 컨테이너 목록 (2개)",
                """\
paperclip-hermes-codex-on-hostinger-tailscale-1            running
paperclip-hermes-codex-on-hostinger-paperclip-hermes-codex-1  running""",
                "text",
            ),
            figure_block("04-containers-running.png", "Docker Manager — 컨테이너 2개 running 상태"),
            check_block(
                "04-3. 확인 기준",
                "컨테이너 2개 모두 <strong>running</strong> 상태입니다. "
                "v0.1 사이드카 구조의 <code>paperclip-init</code> / <code>hermes-init</code>은 v1에서 사라졌습니다 — "
                "권한 설정과 bootstrap이 <code>entrypoint.sh</code> 안으로 통합되었기 때문입니다. "
                "하나라도 <strong>exited</strong>이면 로그 버튼을 눌러 오류 메시지를 확인하세요.",
            ),
            note_block(
                "04-4. 로그 확인 방법",
                "Docker Manager 컨테이너 행 오른쪽 <strong>Logs</strong> 버튼 클릭 → "
                "<code>paperclip-hermes-codex</code> 컨테이너 로그에서 다음 줄을 찾습니다: "
                "<br><code>[entrypoint] Paperclip bootstrap complete</code>"
                "<br><code>[entrypoint] Hermes bootstrap complete</code>"
                "<br><code>[entrypoint] Starting supervisor...</code>",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 05
    # ------------------------------------------------------------------
    {
        "num": "05",
        "title": "Tailscale FQDN 확인 + PAPERCLIP_PUBLIC_URL 재배포",
        "lede": "Tailscale이 노드 FQDN을 할당하면 이를 PAPERCLIP_PUBLIC_URL에 등록하고 재배포합니다. 이 단계를 건너뛰면 로그인 링크에서 403이 납니다.",
        "blocks": [
            code_block(
                "05-1. Tailscale FQDN 확인 방법",
                """\
# 방법 A — Tailscale Admin 콘솔
# https://login.tailscale.com/admin/machines
# → 노드 이름(TS_HOSTNAME)을 찾아 Machine Name(FQDN) 복사
# 예: paperclip.tail1234ab.ts.net

# 방법 B — Docker Manager 로그
# tailscale 컨테이너 로그 → "tailscale up complete" 이후 줄에서
# "https://<fqdn>" 형식으로 노출됩니다.""",
                "bash",
            ),
            figure_block("05-tailscale-fqdn.png", "Tailscale Admin → Machines — 노드 FQDN 확인"),
            code_block(
                "05-2. PAPERCLIP_PUBLIC_URL 값 형식",
                """\
# FQDN이 paperclip.tail1234ab.ts.net 이라면:
PAPERCLIP_PUBLIC_URL=https://paperclip.tail1234ab.ts.net:3100""",
                "bash",
            ),
            note_block(
                "05-3. 왜 재배포가 필요한가",
                "Paperclip은 <code>better-auth</code>를 사용하며, 허용 origin 목록을 부팅 시점의 "
                "<code>PAPERCLIP_PUBLIC_URL</code> 값에서 파생합니다. "
                "이 값이 실제 접근 도메인과 다르면 로그인 시 <strong>Invalid origin / 403</strong>이 발생합니다. "
                "Tailscale FQDN은 첫 배포 이전에는 알 수 없으므로, STEP 04 배포 → FQDN 확인 → 환경변수 갱신 → 재배포 순서가 정상 흐름입니다.",
            ),
            figure_block("05-redeploy-env.png", "환경변수 폼 — PAPERCLIP_PUBLIC_URL 입력 후 재배포"),
            check_block(
                "05-4. 확인 기준",
                "<code>PAPERCLIP_PUBLIC_URL</code>이 <code>https://&lt;fqdn&gt;:3100</code> 형식으로 저장되었고 "
                "컨테이너 2개가 다시 running 상태입니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 06
    # ------------------------------------------------------------------
    {
        "num": "06",
        "title": "첫 접속 — Paperclip 로그인",
        "lede": "브라우저에서 https://<fqdn>:3100 을 열고 ADMIN_EMAIL + ADMIN_PASSWORD로 로그인합니다. 관리자 계정은 entrypoint가 자동 생성했습니다.",
        "blocks": [
            code_block(
                "06-1. 접속 URL",
                """\
# Tailscale 메시에 연결된 디바이스에서 열기
https://<TS_HOSTNAME>.ts.net:3100

# 예시
https://paperclip.tail1234ab.ts.net:3100""",
                "text",
            ),
            note_block(
                "06-2. 관리자 계정 자동 생성 방식",
                "v0.1의 bootstrap-ceo invite token 복사 흐름이 v1에서 사라졌습니다. "
                "<code>entrypoint.sh</code>가 부팅 시 <code>ADMIN_EMAIL</code> + <code>ADMIN_PASSWORD</code> env를 읽어 "
                "Paperclip에 관리자를 자동으로 가입시키고, 이후 <code>disableSignUp: true</code>로 잠급니다. "
                "로그인 페이지에서 가입 버튼이 없으면 정상입니다.",
            ),
            figure_block("06-paperclip-login.png", "Paperclip 로그인 페이지 — ADMIN_EMAIL + ADMIN_PASSWORD 입력"),
            figure_block("06-paperclip-workspace.png", "로그인 후 Paperclip 워크스페이스 메인 화면"),
            check_block(
                "06-3. 확인 기준",
                "Paperclip 워크스페이스 메인 화면이 표시됩니다. "
                "왼쪽 사이드바에 <strong>Agents</strong>, <strong>Tasks</strong>, <strong>Settings</strong> 메뉴가 보입니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 07
    # ------------------------------------------------------------------
    {
        "num": "07",
        "title": "Hermes Dashboard 확인",
        "lede": "새 탭에서 https://<fqdn>:9119 를 열어 Hermes Dashboard에 접속합니다.",
        "blocks": [
            code_block(
                "07-1. Hermes Dashboard URL",
                """\
https://<TS_HOSTNAME>.ts.net:9119

# 예시
https://paperclip.tail1234ab.ts.net:9119""",
                "text",
            ),
            figure_block("07-hermes-dashboard.png", "Hermes Dashboard — Sessions / Skills / API Keys 탭"),
            note_block(
                "07-2. Dashboard가 보여주는 것",
                "Hermes Dashboard는 세션 목록, 설치된 스킬 패키지, API 키 설정, 실행 로그를 제공하는 관리 SPA입니다. "
                "Codex OAuth 완료 전에도 Dashboard 자체는 접근 가능합니다. "
                "ttyd 터미널은 <code>https://&lt;fqdn&gt;:4860</code>에서 열 수 있으며, "
                "접속 시 <code>ADMIN_USERNAME</code> + <code>ADMIN_PASSWORD</code>로 인증합니다.",
            ),
            check_block(
                "07-3. 확인 기준",
                "Hermes Dashboard 메인 화면이 표시됩니다. "
                "상단에 <strong>Sessions</strong> 탭이 보이며, 현재 활성 세션이 없는 상태가 정상입니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 08
    # ------------------------------------------------------------------
    {
        "num": "08",
        "title": "Codex OAuth 부트스트랩",
        "lede": "paperclip-hermes-codex 컨테이너 로그에서 Codex OAuth URL을 찾아 브라우저에서 인증합니다. 이 인증은 단 1회만 필요합니다.",
        "blocks": [
            note_block(
                "08-1. OAuth가 필요한 이유",
                "Hermes는 태스크 실행 시 Codex CLI를 spawn합니다. Codex CLI가 OpenAI API를 호출하려면 "
                "OAuth 토큰 또는 API 키가 있어야 합니다. "
                "<code>codex-oauth.sh</code>는 부팅 시 <code>~/.codex/auth.json</code>을 확인하고, "
                "없으면 <code>codex login --device-auth</code>를 백그라운드로 실행해 URL을 로그에 출력합니다. "
                "Paperclip과 Hermes는 OAuth 완료를 기다리지 않고 즉시 시작됩니다.",
            ),
            code_block(
                "08-2. 컨테이너 로그에서 OAuth URL 찾기",
                """\
# Docker Manager → paperclip-hermes-codex → Logs 버튼 클릭
# 아래와 유사한 줄을 찾습니다:

[codex-oauth] No auth.json found — starting device auth
[codex-oauth] Open this URL to authenticate:
[codex-oauth] https://auth.openai.com/device?user_code=XXXX-XXXX
[codex-oauth] Code: XXXX-XXXX (expires in 15 minutes)""",
                "text",
            ),
            figure_block("08-codex-oauth-log.png", "컨테이너 로그 패널 — Codex OAuth URL + 코드 출력"),
            code_block(
                "08-3. 브라우저 인증 절차",
                """\
# 1. 로그에 표시된 URL을 새 탭에서 엽니다
#    예: https://auth.openai.com/device?user_code=XXXX-XXXX

# 2. ChatGPT 계정으로 로그인 후 "Allow" 클릭

# 3. 콘솔 로그에서 완료 확인:
[codex-oauth] Codex OAuth completed — auth.json saved to /home/node/.codex/auth.json""",
                "bash",
            ),
            figure_block("08-codex-browser-auth.png", "ChatGPT 디바이스 인증 페이지 — Allow 클릭"),
            note_block(
                "08-4. OPENAI_API_KEY 대안",
                "OAuth 대신 API 키를 사용하려면 환경변수 <code>OPENAI_API_KEY=sk-...</code>를 추가하고 재배포합니다. "
                "Codex CLI 0.122 이상은 이 값을 자동으로 <code>auth.json</code> 형식으로 변환합니다. "
                "OAuth와 API 키 중 하나만 있으면 충분하며 두 방식은 혼용 가능합니다.",
            ),
            check_block(
                "08-5. 확인 기준",
                "컨테이너 로그에 <strong>[codex-oauth] Codex OAuth completed</strong>가 출력됩니다. "
                "이후 컨테이너 재시작이나 이미지 업데이트 시 재인증은 필요 없습니다 — "
                "토큰이 <code>codex-auth</code> named volume에 영구 저장되었기 때문입니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 09
    # ------------------------------------------------------------------
    {
        "num": "09",
        "title": "첫 에이전트 생성 + Test now 통과",
        "lede": "Paperclip에서 Hermes Agent 어댑터를 사용하는 CEO 에이전트를 생성하고 Test now 버튼으로 어댑터 환경을 검증합니다.",
        "blocks": [
            code_block(
                "09-1. 에이전트 생성 절차",
                """\
# Paperclip UI (https://<fqdn>:3100)
# 1. 왼쪽 사이드바 → Agents → + New Agent 클릭
# 2. Name: CEO (또는 원하는 이름)
# 3. Adapter: "Hermes Agent" 선택
# 4. Hermes URL: http://localhost:9119  (컨테이너 내부 주소)
# 5. Session Token: Hermes Dashboard → Settings에서 확인
# 6. Save 클릭""",
                "bash",
            ),
            figure_block("09-create-agent.png", "Paperclip — 에이전트 생성 폼, Hermes Agent 어댑터 선택"),
            note_block(
                "09-2. Hermes Agent 어댑터가 동작하는 이유",
                "v1 단일 컨테이너는 <code>hermes</code> 바이너리를 <code>/usr/local/bin</code>에 포함합니다. "
                "Paperclip의 어댑터 환경 체크 (<em>Adapter env check</em>)는 같은 컨테이너 PATH에서 바이너리를 즉시 발견하므로 "
                "추가 설치 없이 바로 통과됩니다.",
            ),
            code_block(
                "09-3. Test now 버튼 클릭 후 기대 결과",
                """\
# 에이전트 상세 페이지 → "Test now" 버튼 클릭
# 성공 시 표시:
Adapter env check: passed""",
                "text",
            ),
            figure_block("09-test-now-passed.png", "Paperclip — Test now 결과: Adapter env check: passed"),
            check_block(
                "09-4. 확인 기준",
                "Test now 버튼 클릭 후 <strong>Adapter env check: passed</strong> 메시지가 표시됩니다. "
                "오류가 나면 <code>paperclip-hermes-codex</code> 컨테이너 로그에서 "
                "<code>[supervisor] hermes dashboard</code> 줄을 확인해 Hermes Dashboard가 실행 중인지 검증합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 10
    # ------------------------------------------------------------------
    {
        "num": "10",
        "title": "첫 Task 실행 — 체인 검증",
        "lede": "간단한 Task를 생성해 Paperclip → Hermes → Codex → OpenAI 전체 체인이 연결되었는지 확인합니다.",
        "blocks": [
            code_block(
                "10-1. Task 생성",
                """\
# Paperclip UI → Tasks → + New Task
# Title: Hello Chain
# Description: Respond with hello
# Agent: CEO (방금 생성한 에이전트)
# Run 클릭""",
                "bash",
            ),
            note_block(
                "10-2. 체인 흐름",
                "Paperclip이 태스크를 Hermes Agent에 전달합니다 → "
                "Hermes는 <code>codex run</code>으로 Codex CLI를 spawn합니다 → "
                "Codex CLI는 <code>auth.json</code> 토큰으로 OpenAI API를 호출합니다 → "
                "결과가 역순으로 전달되어 Paperclip Task 상세 페이지에 반환됩니다.",
            ),
            figure_block("10-task-result.png", "Paperclip Task 상세 — 실행 결과 반환 확인"),
            check_block(
                "10-3. 확인 기준",
                "Task 상세 페이지에 에이전트 응답이 표시됩니다. "
                "Status가 <strong>completed</strong>이면 전체 체인 검증이 완료된 것입니다. "
                "Status가 <strong>failed</strong>이면 STEP 08 Codex OAuth가 완료되었는지 다시 확인합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    # STEP 11
    # ------------------------------------------------------------------
    {
        "num": "11",
        "title": "업데이트 흐름",
        "lede": "Hostinger Docker Manager 콘솔의 Update 버튼 한 번으로 paperclip, hermes, codex 세 도구의 최신 버전이 반영됩니다.",
        "blocks": [
            note_block(
                "11-1. GHA nightly 빌드",
                "GitHub Actions가 매일 KST 12:17에 upstream 이미지를 pull해 "
                "<code>ghcr.io/dandacompany/paperclip-hermes-codex:latest</code>를 재빌드합니다. "
                "Update 버튼은 이 최신 digest를 pull해 컨테이너를 재생성합니다.",
            ),
            code_block(
                "11-2. 콘솔 업데이트 절차",
                """\
# Docker Manager → 서비스 선택 → Update 버튼 클릭
# 내부 동작:
#   docker compose pull          (최신 이미지 다운로드)
#   docker compose up -d         (컨테이너 재생성)
# 소요 시간: 이미지 크기에 따라 1~2분""",
                "bash",
            ),
            figure_block("11-update-button.png", "Docker Manager — Update 버튼 클릭"),
            note_block(
                "11-3. 데이터 보존 원칙",
                "named volume 4개 (<code>paperclip-data</code>, <code>hermes-data</code>, "
                "<code>codex-auth</code>, <code>tailscale-state</code>)는 "
                "<code>docker compose up -d</code>로 컨테이너가 재생성되어도 그대로 유지됩니다. "
                "Codex OAuth 토큰, Hermes 세션·스킬, Paperclip 워크스페이스 데이터, Tailscale 노드 ID가 모두 보존됩니다. "
                "완전히 초기화하려면 Docker Manager → 볼륨 탭에서 4개 볼륨을 수동 삭제합니다.",
            ),
            check_block(
                "11-4. 확인 기준",
                "Update 완료 후 컨테이너 2개가 다시 running 상태입니다. "
                "Paperclip UI에서 기존 Agents와 Tasks가 그대로 보이면 데이터 보존이 정상입니다. "
                "Codex OAuth를 다시 하지 않아도 Task 실행이 정상 동작하면 업데이트가 완료된 것입니다.",
            ),
            note_block(
                "11-5. 특정 버전으로 롤백",
                "GHA 빌드는 <code>:latest</code> 외에 <code>:nightly-&lt;N&gt;</code>와 <code>:&lt;sha&gt;</code> "
                "태그도 publish합니다. 문제가 생기면 Docker Manager 환경변수에서 이미지 태그를 "
                "<code>ghcr.io/dandacompany/paperclip-hermes-codex:nightly-42</code> 형식으로 지정하고 재배포합니다.",
            ),
        ],
    },
]


# ---------------------------------------------------------------------------
# HEAD — HTML + inline CSS (sand/stone/moss palette, Noto Serif/Sans,
#        JetBrains Mono). Reused from v0.1-sidecar HEAD with v1 title update.
# ---------------------------------------------------------------------------

HEAD = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Paperclip + Hermes + Codex — Hostinger 콘솔로 한 페이지에서 끝내기</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;700;900&family=Noto+Sans+KR:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --stone-900:#111111; --stone-700:#2a2a2a; --stone-500:#555555;
      --stone-400:#777777; --stone-200:#c8c4bc;
      --sand-50:#f5f2ec; --sand-100:#ebe5d8; --sand-200:#e0d8c8;
      --moss:#1e3f3f; --moss-light:#2d5555; --cream:#faf7f0;
      --red-soft:#b84a2c; --green-soft:#3a6c49; --terra:#7a5a10;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--sand-50);
      color: var(--stone-700);
      font-family: 'Noto Sans KR', system-ui, sans-serif;
      line-height: 1.75;
    }
    .hero {
      padding: 88px 32px 72px;
      background: linear-gradient(135deg, var(--sand-100), var(--sand-200));
      border-bottom: 1px solid var(--stone-200);
    }
    .hero-inner, .container { max-width: 820px; margin: 0 auto; }
    .eyebrow, .section-num, .block-label, .code-header, th {
      font-family: 'JetBrains Mono', monospace;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .eyebrow {
      display: inline-block;
      margin-bottom: 18px;
      color: var(--moss);
      font-size: 12px;
      font-weight: 500;
    }
    h1, h2 {
      font-family: 'Noto Serif KR', serif;
      color: var(--stone-900);
      line-height: 1.2;
      letter-spacing: 0;
    }
    h1 {
      max-width: 780px;
      margin: 0;
      font-size: clamp(34px, 5vw, 52px);
      font-weight: 900;
    }
    .hero p {
      max-width: 720px;
      margin: 24px 0 0;
      color: var(--stone-500);
      font-size: 17px;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 34px;
    }
    .meta-grid div {
      background: rgba(250, 247, 240, .62);
      border: 1px solid rgba(200, 196, 188, .85);
      border-radius: 16px;
      padding: 16px;
    }
    .meta-grid dt {
      margin: 0 0 4px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--stone-400);
    }
    .meta-grid dd { margin: 0; color: var(--stone-700); font-weight: 600; }
    section.step {
      padding: 68px 0;
      border-top: 1px solid var(--stone-200);
    }
    .section-num {
      color: var(--stone-400);
      font-size: 11px;
      letter-spacing: .35em;
    }
    h2 {
      margin: 10px 0 14px;
      font-size: clamp(24px, 3vw, 32px);
      font-weight: 700;
    }
    .lede { margin: 0 0 28px; color: var(--stone-500); font-size: 16px; }
    .code-block, .note-block, .design-block, .check-block {
      margin: 22px 0;
      border: 1px solid var(--stone-200);
      border-radius: 18px;
      overflow: hidden;
      background: var(--cream);
      box-shadow: 0 18px 50px rgba(17, 17, 17, .05);
    }
    .code-block { background: #111111; border-color: #272727; }
    .code-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 13px 16px;
      border-bottom: 1px solid #272727;
      color: #c8c4bc;
      font-size: 12px;
    }
    .dots { display: flex; gap: 7px; }
    .dots i { width: 11px; height: 11px; border-radius: 999px; display: block; }
    .dots i:nth-child(1) { background: #ff5f57; }
    .dots i:nth-child(2) { background: #ffbd2e; }
    .dots i:nth-child(3) { background: #28c840; }
    pre {
      margin: 0;
      padding: 18px 20px;
      overflow-x: auto;
      white-space: pre;
    }
    code {
      color: #f5f2ec;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      line-height: 1.85;
    }
    .note-block {
      padding: 20px 22px;
      border-left: 5px solid var(--moss);
    }
    .check-block {
      padding: 20px 22px;
      border-left: 5px solid var(--green-soft);
      background: rgba(58, 108, 73, .05);
    }
    .check-block .block-label { color: var(--green-soft); }
    .note-block code, .check-block code, .lede code, p code, td code, li code, a code {
      background: rgba(30, 63, 63, .08);
      color: var(--stone-900);
      padding: 1px 6px;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12.5px;
    }
    .block-label {
      margin-bottom: 10px;
      color: var(--terra);
      font-size: 12px;
      font-weight: 500;
    }
    .note-block p, .design-block p, .check-block p { margin: 0; }
    .design-block { padding: 24px; }
    .goal {
      color: var(--stone-900);
      font-family: 'Noto Serif KR', serif;
      font-size: 20px;
      font-weight: 700;
    }
    .principles {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin: 22px 0;
      padding: 0;
      list-style: none;
    }
    .principles li {
      padding: 16px;
      border: 1px solid var(--stone-200);
      border-radius: 14px;
      background: rgba(245, 242, 236, .65);
    }
    .principles span {
      display: block;
      margin-bottom: 8px;
      color: var(--moss);
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }
    .principles p { color: var(--stone-700); font-size: 14px; }
    .component-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .component-grid article {
      padding: 16px;
      border-radius: 14px;
      background: var(--sand-50);
      border: 1px solid var(--stone-200);
    }
    .component-grid strong { color: var(--stone-900); }
    .component-grid p { margin-top: 8px; color: var(--stone-500); font-size: 14px; }
    table {
      width: 100%;
      margin: 22px 0;
      border-collapse: collapse;
      overflow: hidden;
      border: 1px solid var(--stone-200);
      border-radius: 16px;
      background: var(--cream);
      display: table;
    }
    th, td { padding: 14px 16px; border-bottom: 1px solid var(--stone-200); vertical-align: top; }
    th { color: var(--moss); font-size: 12px; text-align: left; background: var(--sand-100); }
    td { font-size: 14px; color: var(--stone-700); }
    tr:last-child td { border-bottom: 0; }
    a { color: var(--moss-light); }
    a:hover { color: var(--moss); }
    figure.screenshot {
      margin: 28px 0;
      padding: 0;
      border: 1px solid var(--stone-200);
      border-radius: 18px;
      overflow: hidden;
      background: var(--cream);
      box-shadow: 0 18px 50px rgba(17, 17, 17, .05);
      position: relative;
    }
    figure.screenshot img {
      display: block;
      width: 100%;
      height: auto;
      background: var(--sand-100);
    }
    figure.screenshot figcaption {
      padding: 12px 18px;
      border-top: 1px solid var(--stone-200);
      color: var(--stone-500);
      font-size: 13px;
      line-height: 1.55;
      background: var(--cream);
    }
    figure.screenshot .placeholder-tag {
      position: absolute;
      top: 14px;
      right: 14px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(184, 74, 44, .15);
      color: var(--red-soft);
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    footer {
      padding: 50px 32px 70px;
      border-top: 1px solid var(--stone-200);
      color: var(--stone-500);
      text-align: center;
    }
    footer a { color: var(--moss); }
    @media (max-width: 720px) {
      .hero { padding: 58px 22px 48px; }
      .container { padding: 0 22px; }
      .meta-grid, .principles, .component-grid { grid-template-columns: 1fr; }
      section.step { padding: 50px 0; }
      pre { padding: 16px; }
    }
  </style>
</head>
"""


def render_step(section: dict) -> str:
    blocks = "\n".join(section["blocks"])
    return f"""
    <section class="step" id="step-{esc(section['num'])}">
      <div class="section-num">STEP {esc(section['num'])}</div>
      <h2>{esc(section['title'])}</h2>
      <p class="lede">{esc(section['lede'])}</p>
      {blocks}
    </section>
    """


def body() -> str:
    rendered = "\n".join(render_step(section) for section in SECTIONS)
    return f"""
<body>
  <header class="hero">
    <div class="hero-inner">
      <span class="eyebrow">Hostinger Console · Paperclip × Hermes × Codex — v1</span>
      <h1>Paperclip + Hermes + Codex — Hostinger 콘솔로 한 페이지에서 끝내기</h1>
      <p>단일 컨테이너로 묶인 3-도구 스택을 호스팅어 콘솔의 'URL에서 컴포즈 가져오기'로 1분 만에 배포하고, Codex OAuth 1회 인증으로 영구 사용합니다.</p>
      <dl class="meta-grid">
        <div><dt>컨테이너</dt><dd>2개 (paperclip-hermes-codex + tailscale)</dd></div>
        <div><dt>노출 포트</dt><dd>3100 / 9119 / 4860</dd></div>
        <div><dt>인증</dt><dd>ADMIN_* env 자동 + Codex OAuth 1회</dd></div>
        <div><dt>업데이트</dt><dd>콘솔 Update 버튼 1클릭</dd></div>
        <div><dt>데이터 보존</dt><dd>4 named volumes</dd></div>
        <div><dt>호스팅 비용</dt><dd>Hostinger KVM 2 (2 GB RAM 권장)</dd></div>
      </dl>
    </div>
  </header>
  <main class="container">
    {rendered}
  </main>
  <footer>
    <p>저장소 · <a href="https://github.com/dandacompany/paperclip-hermes-codex-on-hostinger">github.com/dandacompany/paperclip-hermes-codex-on-hostinger</a></p>
    <p>v0.1 사이드카 구조 참조 · <code>git checkout v0.1-sidecar</code></p>
    <p>마이그레이션 가이드 · <a href="../MIGRATION-v0.1-to-v1.md">docs/MIGRATION-v0.1-to-v1.md</a></p>
    <p>아키텍처 스펙 · <a href="../superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md">docs/superpowers/specs/2026-05-17-paperclip-hermes-codex-design.md</a></p>
    <p>구현 플랜 · <a href="../superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md">docs/superpowers/plans/2026-05-17-paperclip-hermes-codex-implementation.md</a></p>
    <p>SSH CLI 기반 배포는 <code>docs/tutorial-ssh-cli/</code> 튜토리얼을 참고합니다.</p>
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
