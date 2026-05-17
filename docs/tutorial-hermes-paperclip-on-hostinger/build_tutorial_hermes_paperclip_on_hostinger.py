#!/usr/bin/env python3
from __future__ import annotations

import html
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parent
OUT = BASE / "tutorial-hermes-paperclip-on-hostinger.html"

MASK_PATTERNS = [
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"), "xoxb-<SLACK_TOKEN>"),
    (re.compile(r"xapp-[A-Za-z0-9-]{20,}"), "xapp-<SLACK_APP_TOKEN>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-<API_KEY>"),
    (re.compile(r"tskey-auth-[A-Za-z0-9-]{20,}"), "tskey-auth-<TS_AUTHKEY>"),
    (re.compile(r"\$apr1\$[A-Za-z0-9./]+\$[A-Za-z0-9./]+"), "$apr1$<APR1_HASH>"),
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


SECTIONS = [
    {
        "num": "01",
        "title": "무엇을 설치하는가",
        "lede": "한 Docker 호스트에 Hermes Agent와 Paperclip 컨트롤 플레인을 사이드카로 띄우고, Tailscale 메시 안에서만 접근하게 만듭니다.",
        "blocks": [
            design_block(
                "01-1. 구성",
                "공개 인터넷에 한 포트도 열지 않고, 인증된 메시 멤버에게만 세 인터페이스(Hermes Dashboard · Hermes TUI · Paperclip)를 노출한다.",
                [
                    "Hermes는 LLM 호출, 메시징 게이트웨이, 스킬 실행을 담당한다.",
                    "Paperclip은 작업·라우틴·승인 워크플로를 관리한다.",
                    "두 컨테이너는 같은 Docker 브리지 네트워크에서 서비스 이름으로 직접 통신한다.",
                    "호스트 본인은 127.0.0.1로 직접, 다른 디바이스는 Tailscale 메시로만 접근한다.",
                ],
                [
                    ("Hermes Dashboard", "포트 9119, 세션·API 키·스킬 관리 그래픽 콘솔"),
                    ("Hermes TUI", "포트 4860, ttyd Basic Auth 로 보호되는 웹 터미널"),
                    ("Paperclip Web", "포트 3100, 자체 sign-up 으로 보호되는 작업 워크플로 UI"),
                ],
            ),
            note_block(
                "01-2. 노출 모드 비교",
                "권장 모드는 <strong>tailscale</strong> 입니다 (개인·팀 비공개). 나머지 세 모드는 <code>local</code>(외부 차단), <code>traefik</code>(공개 HTTPS), <code>cloudflared</code>(Cloudflare Tunnel) 이며 설치 후 <code>./setup.sh</code> 재실행으로 갈아탑니다.",
            ),
        ],
    },
    {
        "num": "02",
        "title": "사전 준비",
        "lede": "Docker와 Tailscale 계정이 필요합니다. Apple Silicon Mac은 Rosetta 옵션을 켜둡니다.",
        "blocks": [
            note_block(
                "02-1. 체크리스트",
                "Docker Desktop(macOS·Windows) 또는 Docker Engine(Linux) 가 실행 중입니다. "
                "Apple Silicon Mac 이면 Docker Desktop → Settings → General → "
                "<strong>Use Rosetta for x86_64/amd64 emulation</strong> 가 켜져 있어야 amd64 이미지가 동작합니다. "
                "Tailscale 계정이 있고 (없으면 <a href=\"https://tailscale.com\">tailscale.com</a> 에서 가입), "
                "본인과 공유할 사람들의 디바이스에 Tailscale 클라이언트가 설치되어 같은 tailnet 에 가입되어 있습니다.",
            ),
            note_block(
                "02-2. 본인 호스트는 메시 멤버일 필요 없다",
                "스택을 띄울 노트북·VPS 자체는 Tailscale 클라이언트를 깔지 <strong>않아도</strong> 됩니다. 사이드카 컨테이너가 메시 게이트웨이 역할만 합니다. 본인은 127.0.0.1 로 접속, 다른 디바이스는 메시 FQDN 으로 접속합니다.",
            ),
        ],
    },
    {
        "num": "03",
        "title": "Tailscale auth key 발급",
        "lede": "사이드카가 메시에 가입할 때 한 번 사용하는 인증 키를 만듭니다.",
        "blocks": [
            note_block(
                "03-1. 발급 페이지",
                "<a href=\"https://login.tailscale.com/admin/settings/keys\">login.tailscale.com/admin/settings/keys</a> 로 들어가서 <strong>Generate auth key</strong> 를 누릅니다.",
            ),
            table(
                [
                    ("Reusable", "ON", "사이드카 재생성 시 같은 키로 재가입"),
                    ("Ephemeral", "OFF", "컨테이너가 죽어도 노드가 메시 목록에 남음 (디버깅 편의)"),
                    ("Pre-authorized", "ON", "자동 승인. OFF 면 매 가입 시 콘솔 수동 승인 필요"),
                    ("Expiration", "90 days", "만료 후 새 키 발급 + .env 갱신"),
                ],
                ("옵션", "권장 값", "이유"),
            ),
            code_block(
                "03-2. 발급된 키 형식",
                """
tskey-auth-XXXXXXXXXXXX...
                """,
                "text",
            ),
            note_block(
                "03-3. 키 보관",
                "생성된 키는 한 번만 화면에 표시됩니다. 안전한 곳에 복사해 둡니다. 분실 시 같은 페이지에서 새 키를 발급합니다.",
            ),
        ],
    },
    {
        "num": "04",
        "title": "한 줄 설치",
        "lede": "install.sh 가 저장소를 clone 하고, .env 를 작성하고, 컨테이너를 띄우고, Tailscale 가입 후 Paperclip 의 PUBLIC_URL 까지 자동 갱신합니다.",
        "blocks": [
            code_block(
                "04-1. 설치 명령",
                """
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-paperclip-on-hostinger/main/install.sh \\
  | MODE=tailscale \\
    TS_AUTHKEY=tskey-auth-XXXXXXXXXXXX \\
    ADMIN_EMAIL=you@example.com \\
    bash
                """,
                "bash",
            ),
            note_block(
                "04-2. install.sh 가 하는 일",
                "저장소를 <code>./hermes-paperclip-on-hostinger/</code> 로 clone 합니다. "
                "32자 랜덤 ADMIN_PASSWORD 를 생성해 <code>.env</code> 에 저장합니다 (chmod 600). "
                "<code>docker compose up -d</code> 로 컨테이너 6개를 띄웁니다 (init 2개 + hermes-tui + hermes-dashboard + paperclip + tailscale 사이드카). "
                "사이드카가 메시에 가입한 뒤 실제 tailnet FQDN 을 알아내 <code>PAPERCLIP_PUBLIC_URL</code> 을 갱신하고 paperclip 컨테이너를 재시작합니다.",
            ),
            code_block(
                "04-3. 성공 시 출력 마지막 부분",
                """
  hermes-paperclip-on-hostinger is configured (mode=tailscale).

  URLs:
    Hermes TUI       : (mesh)  https://hermes-paperclip.<your-tailnet>.ts.net:4860  |  (this host)  http://127.0.0.1:4860
    Hermes Dashboard : (mesh)  https://hermes-paperclip.<your-tailnet>.ts.net:9119  |  (this host)  http://127.0.0.1:9119
    Paperclip        : (mesh)  https://hermes-paperclip.<your-tailnet>.ts.net:3100  |  (this host)  http://127.0.0.1:3100

  Credentials (Hermes ttyd + Paperclip admin):
    username : hermes
    email    : you@example.com
    password : U5D7qb8jYuWe0ru7dUMCZ3IsPTqCumYD
    ↑ save it; .env is chmod 600. Rotate later with: ./setup.sh --rotate

==> waiting for Tailscale sidecar to register...
==> tailnet FQDN: hermes-paperclip.tail7b1307.ts.net
==> restarting paperclip with mesh PUBLIC_URL
                """,
                "text",
            ),
            note_block(
                "04-4. 비밀번호 보관",
                "출력에 표시된 password 를 안전한 곳에 복사합니다. 같은 값이 <code>./hermes-paperclip-on-hostinger/.env</code> 의 <code>ADMIN_PASSWORD</code> 라인에 저장되어 있습니다.",
            ),
        ],
    },
    {
        "num": "05",
        "title": "본인 호스트에서 접속",
        "lede": "스택을 띄운 노트북·VPS 자체에서는 127.0.0.1 로 직접 접속합니다. 메시를 거치지 않습니다.",
        "blocks": [
            code_block(
                "05-1. 응답 확인",
                """
curl -sS -o /dev/null -w 'dashboard: %{http_code}\\n' http://127.0.0.1:9119/
curl -sS -u "hermes:$(grep ADMIN_PASSWORD .env | cut -d= -f2-)" \\
     -o /dev/null -w 'tui:       %{http_code}\\n' http://127.0.0.1:4860/
curl -sS -o /dev/null -w 'paperclip: %{http_code}\\n' http://127.0.0.1:3100/
                """,
                "bash",
            ),
            code_block(
                "05-2. 기대 출력",
                """
dashboard: 200
tui:       200
paperclip: 200
                """,
                "text",
            ),
            table(
                [
                    ("Hermes Dashboard", "http://127.0.0.1:9119", "세션·API 키·스킬 관리 GUI"),
                    ("Hermes TUI", "http://127.0.0.1:4860", "ttyd 웹 터미널. 사용자명 hermes, 비번 .env 의 ADMIN_PASSWORD"),
                    ("Paperclip", "http://127.0.0.1:3100", "이메일(ADMIN_EMAIL) + ADMIN_PASSWORD 로 첫 로그인"),
                ],
                ("인터페이스", "URL", "로그인"),
            ),
        ],
    },
    {
        "num": "06",
        "title": "다른 디바이스에서 접속",
        "lede": "Tailscale 클라이언트가 켜진 디바이스(폰·팀원 노트북·다른 PC)에서 메시 FQDN 으로 들어갑니다.",
        "blocks": [
            code_block(
                "06-1. tailnet FQDN 확인",
                """
docker compose exec tailscale tailscale status --json \\
  | python3 -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))"
# 출력 예: hermes-paperclip.tail7b1307.ts.net
                """,
                "bash",
            ),
            table(
                [
                    ("Hermes Dashboard", "https://hermes-paperclip.<your-tailnet>.ts.net:9119", "브라우저로 직접 진입"),
                    ("Hermes TUI", "https://hermes-paperclip.<your-tailnet>.ts.net:4860", "ttyd Basic Auth: hermes / ADMIN_PASSWORD"),
                    ("Paperclip", "https://hermes-paperclip.<your-tailnet>.ts.net:3100", "Paperclip 로그인 폼"),
                ],
                ("인터페이스", "메시 URL", "비고"),
            ),
            note_block(
                "06-2. 인증서",
                "Tailscale 이 <code>.ts.net</code> 도메인용 Let's Encrypt 인증서를 자동 발급합니다. 브라우저 경고가 뜨지 않습니다. 공유 도메인 rate limit 같은 함정도 영향받지 않습니다.",
            ),
            note_block(
                "06-3. 팀원 초대",
                "<a href=\"https://login.tailscale.com/admin/users\">Tailscale admin → Users</a> 에서 <strong>Invite users</strong> 로 이메일을 보냅니다. 초대받은 사람이 Tailscale 가입 + 디바이스 설치 + 같은 tailnet 가입을 마치면 즉시 위 URL 로 접근 가능합니다. (단, Hermes·Paperclip 자체 로그인은 별도로 필요합니다.)",
            ),
        ],
    },
    {
        "num": "07",
        "title": "Hermes 첫 셋업",
        "lede": "Dashboard 또는 TUI 에서 hermes setup 을 한 번 실행해 LLM provider 키와 기본 모델을 등록합니다.",
        "blocks": [
            note_block(
                "07-1. 두 가지 경로",
                "<strong>GUI</strong> — Dashboard(9119) 의 <em>Setup</em> 또는 <em>API Keys</em> 탭에서 클릭으로 등록. "
                "<strong>CLI</strong> — TUI(4860) 또는 호스트 셸에서 <code>docker compose exec hermes-tui hermes setup</code>.",
            ),
            code_block(
                "07-2. CLI 셋업 (옵션)",
                """
docker compose exec hermes-tui /opt/hermes/.venv/bin/hermes setup
# 대화형으로:
#  - LLM provider 선택 (Anthropic / OpenAI / OpenRouter / ...)
#  - API 키 입력
#  - 기본 모델 선택
#  - 저장 → /opt/data/config.yaml 생성
                """,
                "bash",
            ),
            note_block(
                "07-3. 첫 모델 호출 확인",
                "Dashboard 의 Chat 탭 또는 TUI 에서 짧은 문장을 보내 응답이 돌아오는지 확인합니다. 응답이 없으면 API 키 또는 네트워크를 다시 점검합니다.",
            ),
        ],
    },
    {
        "num": "08",
        "title": "Paperclip 첫 사용 + 운영 명령",
        "lede": "Paperclip 에 로그인해 첫 작업을 만들고, 자주 쓰는 운영 명령을 정리합니다.",
        "blocks": [
            note_block(
                "08-1. Paperclip 첫 로그인",
                "Paperclip URL 로 들어가 sign-in 폼에 <strong>ADMIN_EMAIL</strong> 과 <strong>ADMIN_PASSWORD</strong> (.env 의 값) 를 입력합니다. 첫 로그인 시 자동으로 admin 계정이 생성됩니다. 작업·라우틴·승인 흐름은 Paperclip 콘솔에서 진행합니다.",
            ),
            table(
                [
                    ("로그 보기", "docker compose logs -f hermes-dashboard"),
                    ("비밀번호 회전", "./setup.sh --rotate && docker compose up -d --force-recreate hermes-tui hermes-dashboard paperclip"),
                    ("Hermes 메시징 게이트웨이 enable (Slack/Telegram/Discord)", "docker compose --profile gateway up -d"),
                    ("게이트웨이 stop", "docker compose --profile gateway down"),
                    ("이미지 업데이트", "docker compose pull && docker compose up -d"),
                    ("tailnet FQDN 재갱신", "./scripts/refresh-tailnet.sh"),
                    ("모드 전환 (예: local 로)", "MODE=local ADMIN_EMAIL=you@example.com ./setup.sh && docker compose up -d"),
                    ("완전 정리 (데이터 포함)", "docker compose --profile gateway down -v"),
                ],
                ("작업", "명령"),
            ),
            note_block(
                "08-2. 메시 노드 정리",
                "스택을 완전히 회수하면 <a href=\"https://login.tailscale.com/admin/machines\">Tailscale admin → Machines</a> 에서 <code>hermes-paperclip</code> 노드를 <strong>Remove</strong> 합니다. auth key 는 reusable 이라 그대로 유효하며, 영구 무효화하려면 admin 페이지에서 별도 revoke 합니다.",
            ),
            note_block(
                "08-3. 문제가 생기면",
                "Paperclip 이 부팅 직후 죽으면 <code>./scripts/refresh-tailnet.sh</code> 를 실행해 PUBLIC_URL 을 갱신합니다. "
                "메시 멤버에서 도달이 안 되면 디바이스 Tailscale 이 같은 tailnet 인지 <code>tailscale status</code> 로 확인합니다. "
                "그 외 자세한 내역은 저장소의 <code>docs/EXPOSURE-tailscale.md</code> 트러블슈팅 절을 따릅니다.",
            ),
        ],
    },
]


HEAD = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes + Paperclip on Hostinger 설치와 사용법</title>
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
      <span class="eyebrow">Hermes × Paperclip Tutorial</span>
      <h1>Hermes + Paperclip on Hostinger 설치와 사용법</h1>
      <p>한 Docker 호스트에 Hermes Agent 와 Paperclip 컨트롤 플레인을 사이드카로 띄우고, Tailscale 메시 안에서만 인증된 디바이스가 접근하도록 만드는 한 줄 설치 가이드입니다.</p>
      <dl class="meta-grid">
        <div><dt>대상</dt><dd>개인 · 소규모 팀</dd></div>
        <div><dt>노출 모드</dt><dd>Tailscale (권장)</dd></div>
        <div><dt>호스트</dt><dd>노트북 · VPS 공통</dd></div>
      </dl>
    </div>
  </header>
  <main class="container">
    {rendered}
  </main>
  <footer>
    <p>저장소 · <a href="https://github.com/dandacompany/hermes-paperclip-on-hostinger">github.com/dandacompany/hermes-paperclip-on-hostinger</a></p>
    <p>다른 노출 모드는 저장소의 <code>docs/EXPOSURE-traefik.md</code> · <code>docs/EXPOSURE-cloudflared.md</code> · <code>docs/EXPOSURE-tailscale.md</code> 와 Hermes ↔ Paperclip 연동 패턴 <code>docs/INTEGRATION.md</code> 를 참고합니다.</p>
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
