#!/usr/bin/env python3
from __future__ import annotations

import html
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parent
OUT = BASE / "tutorial-hostinger-console.html"

MASK_PATTERNS = [
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"), "xoxb-<SLACK_TOKEN>"),
    (re.compile(r"xapp-[A-Za-z0-9-]{20,}"), "xapp-<SLACK_APP_TOKEN>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-<API_KEY>"),
    (re.compile(r"tskey-auth-[A-Za-z0-9-]{20,}"), "tskey-auth-<TS_AUTHKEY>"),
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def mask(text: str) -> str:
    for pattern, repl in MASK_PATTERNS:
        text = pattern.sub(repl, text)
    return text


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
    """Render a screenshot figure. Falls back to placeholder SVG if file missing."""
    asset_dir = BASE / "assets"
    target = asset_dir / filename
    src = filename if target.exists() else "assets/placeholder.svg"
    label = filename if not target.exists() else ""
    label_html = f"<span class=\"placeholder-tag\">PLACEHOLDER · {esc(label)}</span>" if label else ""
    return f"""
    <figure class="screenshot">
      <img src="assets/{esc(src) if target.exists() else 'placeholder.svg'}" alt="{esc(caption)}" loading="lazy">
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


# Self-contained compose YAML for hPanel paste — no external file
# mounts. The tailscale sidecar pulls its serve config from GitHub Raw
# at boot, so the whole stack is one paste-able YAML.
COMPOSE_YAML = """\
name: hermes-paperclip

services:
  hermes-init:
    image: ghcr.io/hostinger/hvps-hermes-agent:latest
    platform: linux/amd64
    user: "0:0"
    entrypoint: ["sh", "-c"]
    command:
      - |
        set -e
        mkdir -p /opt/data
        chown -R 10000:10000 /opt/data
        echo "hermes-init: ready"
    volumes:
      - hermes-data:/opt/data
    restart: "no"

  paperclip-init:
    image: ghcr.io/hostinger/hvps-paperclip:latest
    platform: linux/amd64
    user: "0:0"
    entrypoint: ["sh", "-c"]
    command:
      - |
        set -e
        mkdir -p /paperclip
        chown -R 1000:1000 /paperclip
        echo "paperclip-init: ready"
    volumes:
      - paperclip-data:/paperclip
    restart: "no"

  hermes-tui:
    image: ghcr.io/hostinger/hvps-hermes-agent:latest
    platform: linux/amd64
    restart: unless-stopped
    depends_on:
      hermes-init:
        condition: service_completed_successfully
    environment:
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        exec gosu hermes ttyd \\
          --port 4860 \\
          -c "$$ADMIN_USERNAME:$$ADMIN_PASSWORD" \\
          -W \\
          -t titleFixed="Hermes Agent" \\
          -t disableResizeOverlay=true \\
          /hermes.sh
    volumes:
      - hermes-data:/opt/data

  hermes-dashboard:
    image: ghcr.io/hostinger/hvps-hermes-agent:latest
    platform: linux/amd64
    restart: unless-stopped
    depends_on:
      hermes-init:
        condition: service_completed_successfully
    user: "10000:10000"
    entrypoint: ["/opt/hermes/.venv/bin/hermes"]
    command:
      - "dashboard"
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "9119"
      - "--no-open"
      - "--skip-build"
      - "--insecure"
    environment:
      HERMES_HOME: /opt/data
    volumes:
      - hermes-data:/opt/data

  paperclip:
    image: ghcr.io/hostinger/hvps-paperclip:latest
    platform: linux/amd64
    restart: unless-stopped
    depends_on:
      paperclip-init:
        condition: service_completed_successfully
    environment:
      ADMIN_NAME: ${ADMIN_NAME:-Owner}
      ADMIN_EMAIL: ${ADMIN_EMAIL}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      PAPERCLIP_PUBLIC_URL: ${PAPERCLIP_PUBLIC_URL:-http://localhost:3100}
      PAPERCLIP_INSTANCE_ID: default
    volumes:
      - paperclip-data:/paperclip

  tailscale:
    image: tailscale/tailscale:latest
    hostname: ${TS_HOSTNAME:-hermes-paperclip}
    restart: unless-stopped
    environment:
      TS_AUTHKEY: ${TS_AUTHKEY}
      TS_STATE_DIR: /var/lib/tailscale
      TS_USERSPACE: "false"
      TS_EXTRA_ARGS: "--ssh --accept-routes"
      TS_SERVE_CONFIG: /config/serve.json
    entrypoint: ["sh", "-c"]
    command:
      - |
        mkdir -p /config
        wget -qO /config/serve.json \\
          https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/tailscale/serve.json
        exec /usr/local/bin/containerboot
    volumes:
      - tailscale-state:/var/lib/tailscale
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - NET_ADMIN
      - NET_RAW
    depends_on:
      hermes-dashboard:
        condition: service_started
      hermes-tui:
        condition: service_started
      paperclip:
        condition: service_started

volumes:
  hermes-data:
  paperclip-data:
  tailscale-state:
"""


SECTIONS = [
    {
        "num": "01",
        "title": "무엇을 설치하는가",
        "lede": "Hostinger VPS 의 Docker Manager 콘솔에서 직접 컴포즈 한 벌을 붙여넣어 Hermes 와 Paperclip 을 사이드카로 띄웁니다. SSH 명령은 없습니다.",
        "blocks": [
            design_block(
                "01-1. 구성",
                "Hostinger 콘솔 UI 만으로 두 시스템과 Tailscale 게이트웨이를 한 프로젝트로 배포한다.",
                [
                    "Hermes Dashboard (9119) · Hermes TUI (4860) · Paperclip (3100) 세 서비스를 한 프로젝트에서 운영한다.",
                    "Tailscale 사이드카가 메시 게이트웨이가 되어, 외부 인터넷에는 한 포트도 노출하지 않는다.",
                    "환경변수와 비밀번호는 Hostinger 콘솔의 변수 입력 폼으로 직접 등록한다.",
                    "재시작·로그·업데이트는 Docker Manager 페이지의 버튼으로 처리한다.",
                ],
                [
                    ("hPanel", "Hostinger 웹 콘솔. VPS · 도메인 · Docker Manager 진입점"),
                    ("Docker Manager", "VPS 한 대의 컴포즈 프로젝트 목록을 관리하는 페이지"),
                    ("Tailscale 메시", "인증된 디바이스만 보이는 사설 네트워크. 공개 도메인 불필요"),
                ],
            ),
            note_block(
                "01-2. 이 경로가 맞는 경우",
                "Hostinger VPS 를 처음 다루고 SSH 보다 웹 콘솔이 편한 운영자에게 맞습니다. "
                "이미 SSH 가 익숙하다면 저장소의 <code>install.sh</code> 한 줄 설치를 쓰는 게 더 빠릅니다 "
                "(<code>docs/tutorial-hermes-paperclip-on-hostinger/</code> 참고).",
            ),
        ],
    },
    {
        "num": "02",
        "title": "Tailscale auth key 발급",
        "lede": "사이드카가 메시에 가입할 때 사용하는 인증 키를 미리 만들어 둡니다.",
        "blocks": [
            note_block(
                "02-1. 발급 페이지",
                "<a href=\"https://login.tailscale.com/admin/settings/keys\">login.tailscale.com/admin/settings/keys</a> 로 이동해 <strong>Generate auth key</strong> 를 누릅니다.",
            ),
            table(
                [
                    ("Reusable", "ON"),
                    ("Ephemeral", "OFF"),
                    ("Pre-authorized", "ON"),
                    ("Expiration", "90 days"),
                ],
                ("옵션", "권장 값"),
            ),
            note_block(
                "02-2. 키 보관",
                "<code>tskey-auth-...</code> 로 시작하는 문자열을 한 번만 화면에 보여줍니다. 4단계에서 환경변수로 입력해야 하므로 안전한 곳에 복사해 둡니다.",
            ),
        ],
    },
    {
        "num": "03",
        "title": "Hostinger Docker Manager 진입",
        "lede": "hPanel 에서 대상 VPS 의 Docker Manager 페이지로 들어갑니다.",
        "blocks": [
            note_block(
                "03-1. 경로",
                "<a href=\"https://hpanel.hostinger.com\">hpanel.hostinger.com</a> 에 로그인한 뒤 "
                "왼쪽 메뉴 <strong>VPS</strong> → 사용할 서버 카드의 <strong>Manage</strong> → "
                "왼쪽 사이드바 <strong>Docker Manager</strong> 로 이동합니다.",
            ),
            note_block(
                "03-2. Traefik 사전 준비 불필요",
                "Traefik 설치는 필요 없습니다. 빈 VPS 에서 바로 시작해도 됩니다. "
                "기존에 다른 Docker Manager 앱이 깔려 있어도 충돌하지 않습니다 (다른 프로젝트 이름·다른 볼륨).",
            ),
            note_block(
                "03-3. 빈 프로젝트 화면",
                "처음 진입하면 <strong>첫 배포를 시작하세요</strong> 안내가 보입니다. 가운데의 검은색 <strong>컴포즈</strong> 버튼을 누르면 3가지 방식이 펼쳐집니다.",
            ),
            figure_block("01-hpanel-vps.png", "VPS 목록 페이지에서 사용할 서버의 관리 진입."),
            figure_block("02-docker-manager.png", "Docker Manager 의 빈 프로젝트 상태 (첫 배포 안내 + 컴포즈 버튼)."),
        ],
    },
    {
        "num": "04",
        "title": "URL 에서 컴포즈 가져오기",
        "lede": "컴포즈 드롭다운의 3가지 옵션 중 <strong>URL 에서 컴포즈 가져오기</strong> 를 선택합니다. 이 저장소의 Raw URL 을 붙여넣기만 하면 됩니다.",
        "blocks": [
            note_block(
                "04-1. 3가지 옵션 중 가운데",
                "<strong>수동으로 컴포즈 구성</strong> 은 textarea 에 직접 YAML 을 붙여넣는 방식, "
                "<strong>원클릭 배포</strong> 는 Hostinger 가 제공하는 단일 앱 템플릿입니다. "
                "이 경우 <strong>URL 에서 컴포즈 가져오기</strong> 가 가장 빠릅니다 — 텍스트 없이 한 줄 입력으로 끝납니다.",
            ),
            figure_block("03-compose-options.png", "컴포즈 드롭다운 — 가운데 URL 에서 컴포즈 가져오기 선택."),
            code_block(
                "04-2. 컴포즈 URL",
                """
https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/docker-compose.console.yml
                """,
                "text",
            ),
            note_block(
                "04-3. URL · 프로젝트 이름 입력",
                "<strong>URL</strong> 필드에 위 Raw URL 을 붙여넣고, "
                "<strong>프로젝트 이름</strong> 은 <code>hermes-paperclip-on-hostinger</code> 또는 본인이 원하는 짧은 이름으로 입력합니다. "
                "오른쪽 패널에 GitHub · GitLab · Docker Compose 아이콘이 보이는 게 정상 — Hostinger 가 입력한 URL 의 출처를 자동 인식한 표시입니다. "
                "<strong>배포</strong> 버튼을 누르면 다음 단계(환경변수 입력)로 넘어갑니다.",
            ),
            figure_block("04-compose-url-input.png", "URL · 프로젝트 이름 입력 후 배포 버튼 — 빨간 박스 위치 그대로 따라 입력."),
            note_block(
                "04-4. 무엇이 들어 있나",
                "단일 self-contained 파일로 init 컨테이너 2개, Hermes TUI · Dashboard, Paperclip, Tailscale 사이드카까지 모두 정의되어 있습니다. "
                "Tailscale 사이드카는 부팅 직후 같은 저장소의 <code>tailscale/serve.json</code> 라우팅 파일을 GitHub Raw 에서 받아 적용하므로 추가 파일 업로드가 필요 없습니다. "
                "두 Hostinger 이미지에 <code>platform: linux/amd64</code> 가 박혀 있어 VPS 에서 그대로 부팅됩니다.",
            ),
        ],
    },
    {
        "num": "05",
        "title": "환경변수 입력",
        "lede": "컴포즈를 가져온 다음 화면에서 6개 변수를 등록합니다. 비밀번호는 미리 32자 랜덤 문자열로 만들어 둡니다.",
        "blocks": [
            code_block(
                "05-1. 비밀번호를 미리 만든다 (호스트 어디서나 한 번)",
                """
# macOS / Linux 어디서나 한 줄로 32자 랜덤 비밀번호 생성
openssl rand -base64 32 | tr -d '/+=' | head -c 32 ; echo
                """,
                "bash",
            ),
            table(
                [
                    ("ADMIN_USERNAME", "hermes", "Hermes TUI Basic Auth 사용자명"),
                    ("ADMIN_NAME", "Owner", "Paperclip 첫 admin 표시 이름"),
                    ("ADMIN_EMAIL", "you@example.com", "Paperclip 첫 로그인 이메일"),
                    ("ADMIN_PASSWORD", "<32-char random>", "Hermes TUI · Paperclip 공통 비밀번호"),
                    ("TS_AUTHKEY", "tskey-auth-...", "2단계에서 발급한 키"),
                    ("TS_HOSTNAME", "hermes-paperclip", "Tailscale 노드 표시 이름"),
                ],
                ("변수명", "값 예시", "용도"),
            ),
            note_block(
                "05-2. PAPERCLIP_PUBLIC_URL 은 비워둔다",
                "5단계에서는 이 변수를 등록하지 않거나 임시로 <code>http://localhost:3100</code> 으로 둡니다. "
                "Tailscale 메시에 가입한 뒤 진짜 FQDN 을 알게 되면 7단계에서 갱신합니다.",
            ),
            note_block(
                "05-3. 변수 입력 후 저장",
                "콘솔의 <strong>Save</strong> 또는 <strong>Add variable</strong> 행동으로 6개 모두 등록합니다. 이 시점엔 컨테이너가 아직 부팅 안 됩니다.",
            ),
            figure_block("05-env-vars.png", "환경 탭 — 빨간 박스로 강조된 ADMIN_USERNAME · ADMIN_NAME · ADMIN_EMAIL · ADMIN_PASSWORD · TS_AUTHKEY · TS_HOSTNAME 여섯 줄을 입력 후 저장 후 배포."),
        ],
    },
    {
        "num": "06",
        "title": "Deploy + 컨테이너 상태 확인",
        "lede": "Deploy 후 Docker Manager 에 컨테이너 카드 6장이 뜹니다. 4장은 Running, 2장은 Exited 가 정상 상태입니다.",
        "blocks": [
            note_block(
                "06-1. Deploy",
                "콘솔의 <strong>Deploy</strong> 또는 <strong>Start</strong> 버튼을 누릅니다. "
                "Hostinger 가 이미지를 pull 하고 컨테이너 6개를 띄웁니다 (약 1~3분, 첫 pull 일수록 더 걸림).",
            ),
            note_block(
                "06-2. 정상 부팅 시 상태 — 4 Running + 2 Exited",
                "<strong>Running 4 개</strong> · <code>hermes-tui</code> (ttyd 콘솔), <code>hermes-dashboard</code> (Hermes 그래픽 UI), <code>paperclip</code> (Paperclip 워크플로 UI), <code>tailscale</code> (메시 게이트웨이). "
                "<strong>Exited 2 개</strong> · <code>hermes-init</code> 과 <code>paperclip-init</code> 은 데이터 볼륨 소유권을 한 번 정리하고 종료하도록 설계된 init 컨테이너입니다 — Exited 가 정상 상태이며 종료 코드는 <code>0</code> 입니다. "
                "init 이 정상 종료해야 의존성 조건(<code>service_completed_successfully</code>)을 통해 나머지 4 개가 부팅됩니다.",
            ),
            note_block(
                "06-3. 첫 부팅에서 Paperclip 이 재시작 루프인 경우",
                "5-2 에서 <code>PAPERCLIP_PUBLIC_URL</code> 을 비웠을 때 정상 동작이지만, "
                "잘못된 값(예: placeholder URL) 을 넣으면 better-auth 가 거부해 재시작 루프에 빠집니다. "
                "그럴 땐 <code>http://localhost:3100</code> 으로 임시 수정 후 Restart.",
            ),
            note_block(
                "06-4. Tailscale 사이드카 로그 확인",
                "<code>tailscale</code> 컨테이너 카드의 <strong>Logs</strong> 를 열어 "
                "<em>Switching ipn state Starting -> Running</em> 과 "
                "<em>serve: creating a new proxy handler for http://hermes-dashboard:9119</em> 등 3개의 proxy handler 로그를 확인합니다.",
            ),
            figure_block("06-containers.png", "컨테이너 카드 6 장 — 빨간 박스 안의 Running 4 개와 Exited 2 개 (init 컨테이너가 초기화 작업 후 자동 종료된 상태). Exited 옆에 음수 종료 코드가 없다면 정상."),
            figure_block("07-logs.png", "컨테이너 카드의 터미널/Logs 버튼으로 본 부팅 로그. 위 hermes-tui 의 ttyd 4860 LISTEN, 아래 paperclip 의 bootstrap CEO invite URL · PostgreSQL ready · plugin coordinator 시작."),
        ],
    },
    {
        "num": "07",
        "title": "메시 FQDN 확인 + 세 인터페이스 접속",
        "lede": "Tailscale admin 콘솔에서 노드 도메인을 확정하고, 같은 tailnet 멤버 디바이스에서 Hermes · Paperclip · TUI 세 인터페이스를 차례로 엽니다.",
        "blocks": [
            note_block(
                "07-1. 메시 노드 확인 — 머신 목록",
                "<a href=\"https://login.tailscale.com/admin/machines\">login.tailscale.com/admin/machines</a> 머신 목록에서 "
                "<code>hermes-paperclip</code> (또는 지정한 <code>TS_HOSTNAME</code>) 행을 찾습니다. "
                "Address 컬럼의 100.x.x.x 가 mesh IP, LAST SEEN 이 Connected 면 가입 성공입니다.",
            ),
            figure_block("08-tailscale-list.png", "Tailscale admin → Machines 의 머신 목록. 빨간 박스의 hermes-paperclip 행이 우리 사이드카 노드 (datapod.k@gmail.com 소유, 100.107.239.62, Linux, Connected)."),
            note_block(
                "07-2. 노드 클릭 → 상세 페이지에서 Full domain 확인",
                "목록의 hermes-paperclip 행을 클릭해 상세 페이지로 들어가면 <strong>Machine Details</strong> 섹션에 "
                "<strong>Full domain</strong> 항목이 보입니다. 이 값(예: <code>hermes-paperclip.tail7b1307.ts.net</code>) 이 "
                "메시 멤버 디바이스에서 접속할 때 쓰는 호스트명입니다. Copy 버튼으로 클립보드에 복사해 둡니다.",
            ),
            figure_block("09-tailscale-detail.png", "hermes-paperclip 상세 페이지의 Machine Details — 빨간 박스의 Full domain 값(hermes-paperclip.tail7b1307.ts.net)이 이후 단계에서 쓰는 메시 호스트명."),
            note_block(
                "07-2b. PAPERCLIP_PUBLIC_URL 을 Full domain 으로 즉시 갱신",
                "Paperclip 의 better-auth 는 <code>PAPERCLIP_PUBLIC_URL</code> 한 값에서 trusted origin 6 종을 derive 합니다. "
                "이 값이 <code>http://localhost:3100</code> 인 상태로 메시 도메인에서 접근하면 sign-up 페이지가 <strong>Invalid origin / 403</strong> 으로 거부합니다. "
                "Docker Manager → 환경 탭에서 <code>PAPERCLIP_PUBLIC_URL</code> 을 "
                "<code>https://&lt;Full-domain&gt;:3100</code> (예: <code>https://hermes-paperclip.tail7b1307.ts.net:3100</code>) 으로 저장하고 "
                "<code>paperclip</code> 컨테이너만 Restart. 이후 invite URL 접근이 통과됩니다.",
            ),
            note_block(
                "07-3. 디바이스 측 Tailscale 준비",
                "접속하려는 노트북·폰에 Tailscale 클라이언트가 설치되어 있고 같은 tailnet 에 가입되어 있어야 합니다. "
                "다른 tailnet 이면 같은 IP·도메인이라도 안 보입니다. "
                "팀원 초대는 <a href=\"https://login.tailscale.com/admin/users\">admin → Users → Invite users</a> 에서 이메일 발송.",
            ),
            table(
                [
                    ("Hermes Dashboard", "https://<Full-domain>:9119", "별도 로그인 없음 (Hermes 자체 세션 토큰)"),
                    ("Hermes TUI", "https://<Full-domain>:4860", "Basic Auth: hermes / ADMIN_PASSWORD"),
                    ("Paperclip", "https://<Full-domain>:3100", "첫 접속은 invite URL 로 admin 등록 (07-5 참고), 이후 sign-in"),
                ],
                ("인터페이스", "메시 URL", "첫 진입 인증"),
            ),
            note_block(
                "07-4. Hermes Dashboard 첫 진입",
                "<code>:9119</code> 로 들어가면 Hermes 자체 세션 토큰이 자동 발급되어 별도 로그인 없이 메인 화면이 열립니다. "
                "왼쪽 사이드바의 <strong>Sessions · Analytics · Models · Logs · Cron · Skills · Plugins · Profiles · Config · Keys · Documentation</strong> 메뉴 중 "
                "<strong>Keys</strong> 에서 LLM provider API 키를 등록하고, <strong>Sessions</strong> 탭에서 첫 모델 호출을 검증합니다. "
                "하단의 <strong>Gateway Status · Active Sessions</strong> 표시로 메시징 게이트웨이 상태를 한눈에 확인합니다.",
            ),
            figure_block("10-hermes-dashboard.png", "Hermes Dashboard 메인 — 왼쪽 사이드바의 풀 메뉴, 가운데 Sessions 탭 (NO SESSIONS YET 안내), 하단 System 패널 (Gateway Status · Active Sessions)."),
            note_block(
                "07-5. Paperclip 첫 접속 — Bootstrap invite 흐름",
                "<code>:3100</code> 첫 진입 시 sign-in 폼 대신 <strong>Instance setup required — A bootstrap invite is already active</strong> 안내가 보일 수 있습니다. "
                "Paperclip 은 첫 부팅 때 발급된 <strong>일회용 invite URL 로만 admin 을 등록</strong>합니다 (env 의 ADMIN_PASSWORD 만으로는 자동 가입되지 않음). "
                "<code>paperclip</code> 컨테이너의 Logs 를 열어 <code>Invite URL: http://localhost:3100/invite/pcp_bootstrap_…</code> 줄을 찾고, "
                "<code>localhost:3100</code> 부분을 메시 Full domain 으로 바꿔 접속합니다 "
                "(예: <code>https://&lt;Full-domain&gt;:3100/invite/pcp_bootstrap_…</code>).",
            ),
            figure_block("11-paperclip-invite-signup.png", "invite URL 첫 진입 — 좌측 'Set up Paperclip' 패널은 company · invited by · requested access · invite expires 안내, 우측 'Create your account' 폼에서 Name · Email · Password 를 입력하고 Create account and continue."),
            note_block(
                "07-5b. 가입 후 흐름",
                "Create account 버튼을 누르면 admin 계정이 만들어지고 invite 가 소진됩니다. "
                "이후 같은 <code>:3100</code> URL 은 일반 sign-in 폼으로 전환되며, 다음 로그인부터는 방금 등록한 email · password 로 들어갑니다. "
                "Paperclip Logs 에 새로 찍히는 <code>auth: instance admin registered</code> 같은 줄로도 가입 완료를 확인할 수 있습니다.",
            ),
            note_block(
                "07-6. invite 가 만료 · 사용됨 · 차단됐다면 — rotate 명령",
                "<strong>Invite not available — This invite may be expired, revoked, or already used.</strong> "
                "안내가 보이면 컨테이너 안에서 새 invite 를 발급합니다. "
                "Docker Manager 의 <code>paperclip</code> 컨테이너 카드 <strong>터미널</strong> 또는 SSH 로: "
                "<code>docker exec hermes-paperclip-on-hostinger-paperclip-1 paperclipai auth bootstrap-ceo</code>. "
                "출력의 <code>Invite URL</code> 한 줄에 새 토큰 + 메시 도메인이 그대로 나옵니다 (07-2b 의 PAPERCLIP_PUBLIC_URL 덕분). "
                "새 URL 을 브라우저로 열면 Set up Paperclip 페이지가 정상 열림.",
            ),
            figure_block("12-paperclip-workspace.png", "Paperclip admin sign-up 완료 후 워크스페이스 메인 또는 sign-in 페이지."),
            note_block(
                "07-7. PAPERCLIP_PUBLIC_URL 의 역할 정리",
                "07-2b 에서 갱신한 <code>PAPERCLIP_PUBLIC_URL</code> 한 값이 다음 네 군데를 동시에 결정합니다. "
                "(1) better-auth trusted origin 목록 (메시 도메인 접근 허용), "
                "(2) 이메일 magic link / 초대장 URL, "
                "(3) OAuth callback URL, "
                "(4) Paperclip UI 가 절대 URL 을 생성할 때 prefix. "
                "단일 source of truth — 도메인 변경 시 이 한 줄만 바꾸면 됩니다.",
            ),
        ],
    },
    {
        "num": "08",
        "title": "Hermes · Paperclip 첫 사용 + 운영",
        "lede": "두 시스템 모두 자체 로그인을 가지고 있습니다. 첫 셋업과 자주 쓰는 운영 동작을 정리합니다.",
        "blocks": [
            note_block(
                "08-1. Hermes 첫 셋업",
                "Dashboard URL (<code>:9119</code>) 로 들어가 <strong>Setup</strong> 또는 <strong>API Keys</strong> 탭에서 "
                "LLM provider (Anthropic / OpenAI / OpenRouter / ...) 키와 기본 모델을 등록합니다. "
                "TUI 에서 셸로 진행하려면 Docker Manager 의 <code>hermes-tui</code> 컨테이너 카드의 "
                "<strong>Console</strong> 또는 <strong>Exec</strong> 버튼으로 <code>hermes setup</code> 을 실행합니다.",
            ),
            note_block(
                "08-2. Paperclip 첫 로그인",
                "Paperclip URL (<code>:3100</code>) 로 들어가 sign-in 폼에 "
                "<code>ADMIN_EMAIL</code> 과 <code>ADMIN_PASSWORD</code> (5단계에서 입력한 값) 를 넣습니다. "
                "첫 로그인 시 admin 계정이 자동 생성됩니다. "
                "Paperclip 컨테이너 로그 상단에 <code>pcp_bootstrap_…</code> 로 시작하는 일회용 admin invite URL 이 한 번 찍히는데, 첫 로그인이 끝나면 즉시 소진됩니다 — 외부에 공유하지 마세요.",
            ),
            table(
                [
                    ("재시작", "Docker Manager → 프로젝트 → Restart"),
                    ("개별 컨테이너 재시작", "컨테이너 카드의 Restart 버튼"),
                    ("로그 보기", "컨테이너 카드의 Logs 버튼"),
                    ("환경변수 변경", "프로젝트의 Environment 탭에서 수정 → Save → Restart"),
                    ("이미지 업데이트", "프로젝트의 Update 또는 Pull 버튼 (Pull 후 Restart)"),
                    ("비밀번호 회전", "ADMIN_PASSWORD 새 값 입력 → Save → hermes-tui · paperclip 재시작"),
                    ("완전 정리 (데이터 포함)", "프로젝트의 Delete (Down with volumes 옵션 선택)"),
                ],
                ("작업", "콘솔 동작"),
            ),
            note_block(
                "08-3. 메시 노드 정리",
                "Hostinger 에서 프로젝트를 지운 뒤 <a href=\"https://login.tailscale.com/admin/machines\">Tailscale admin → Machines</a> 에서 "
                "<code>hermes-paperclip</code> 노드를 <strong>Remove</strong> 해 메시 목록에서 빼냅니다. "
                "auth key 는 reusable 이라 그대로 유효합니다.",
            ),
            note_block(
                "08-4. 문제가 생기면",
                "Paperclip sign-up 페이지에서 <strong>Invalid origin / 403</strong> 이 보이면 <code>PAPERCLIP_PUBLIC_URL</code> 이 접근 도메인과 다른 상태입니다 (07-2b 참고). "
                "Paperclip 이 부팅 직후 죽으면 <code>PAPERCLIP_PUBLIC_URL</code> 값이 잘못된 URL 형식이라는 뜻입니다 (better-auth 가 invalid base URL 거부). "
                "메시 Full domain 으로 갱신하거나 <code>http://localhost:3100</code> 으로 임시 복구. "
                "그 외 항목은 저장소의 <code>docs/EXPOSURE-tailscale.md</code> 트러블슈팅 절을 따릅니다.",
            ),
        ],
    },
]


HEAD = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hostinger 콘솔로 Hermes + Paperclip 배포하기</title>
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
    .code-block, .note-block, .design-block {
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
    .note-block code, .lede code, p code, td code, li code, a code {
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
    .note-block p, .design-block p { margin: 0; }
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
      <span class="eyebrow">Hostinger Console · Hermes × Paperclip</span>
      <h1>Hostinger 콘솔로 Hermes + Paperclip 배포하기</h1>
      <p>Hostinger VPS 의 Docker Manager 페이지에서 컴포즈 한 벌을 붙여넣고 환경변수만 입력해 Hermes 와 Paperclip 을 사이드카로 띄웁니다. Tailscale 메시 안에서만 인증된 디바이스가 접근하고, 운영도 같은 콘솔에서 끝납니다.</p>
      <dl class="meta-grid">
        <div><dt>대상</dt><dd>Hostinger VPS 사용자</dd></div>
        <div><dt>도구</dt><dd>hPanel Docker Manager</dd></div>
        <div><dt>SSH</dt><dd>불필요</dd></div>
      </dl>
    </div>
  </header>
  <main class="container">
    {rendered}
  </main>
  <footer>
    <p>저장소 · <a href="https://github.com/dandacompany/hermes-paperclip-on-hostinger">github.com/dandacompany/hermes-paperclip-on-hostinger</a></p>
    <p>SSH 기반 한 줄 설치 흐름은 <code>docs/tutorial-hermes-paperclip-on-hostinger/</code> 튜토리얼을 참고합니다.</p>
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
