#!/usr/bin/env python3
"""Build script for the manual install tutorial.

Produces docs/tutorial-manual-install/tutorial-manual-install.html.

Source markdown: docs/manual-install-on-one-click-paperclip.md
Sibling for HEAD + render reuse: docs/tutorial-hostinger-console/build_tutorial_hostinger_console.py
"""
from __future__ import annotations

import importlib.util
import pathlib

BASE = pathlib.Path(__file__).resolve().parent
OUT = BASE / "tutorial-manual-install.html"

# ---------------------------------------------------------------------------
# Reuse HEAD + render helpers from the sibling Hostinger-console tutorial
# ---------------------------------------------------------------------------
_SIBLING = BASE.parent / "tutorial-hostinger-console/build_tutorial_hostinger_console.py"
_spec = importlib.util.spec_from_file_location("_console_tutorial", _SIBLING)
_te = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_te)

HEAD = _te.HEAD.replace(
    "<title>Paperclip + Hermes + Codex — Hostinger 콘솔로 한 페이지에서 끝내기</title>",
    "<title>Paperclip + Hermes + Codex — Hostinger 원클릭 위에 수동 설치</title>",
)

esc          = _te.esc
mask         = _te.mask
code_block   = _te.code_block
note_block   = _te.note_block
check_block  = _te.check_block
design_block = _te.design_block
table        = _te.table
render_step  = _te.render_step


# Resolve placeholder relative to THIS tutorial's BASE
def figure_block(filename: str, caption: str) -> str:
    if filename.startswith(("http://", "https://")):
        src = filename
        label_html = ""
        return f"""
    <figure class="screenshot">
      <img src="{src}" alt="{esc(caption)}" loading="lazy">
      <figcaption>{esc(caption)}</figcaption>
    </figure>
    """
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
# SECTIONS — 17개 step (사전 준비 + 12 본설치 + Troubleshooting + 프롬프트 + Update)
# ---------------------------------------------------------------------------

SECTIONS = [
    # ------------------------------------------------------------------
    {
        "num": "01",
        "title": "사전 준비 + 구조 개요",
        "lede": "Hostinger 원클릭 Paperclip 컨테이너 위에 Hermes Agent와 Codex CLI를 얹는 구조입니다. host bind mount(`./data/tools/`)에 보조 binary와 init 스크립트를 두고, Hostinger Update 버튼이 컨테이너를 재생성해도 매 부팅마다 자동 복구됩니다.",
        "blocks": [
            design_block(
                "01-1. 통합 구조",
                goal="Tailscale 메시 → Paperclip 컨테이너 안 init.sh가 Hermes·ttyd 결합 → ChatGPT Codex backend로 LLM 호출",
                principles=[
                    "외부 노출 0 — Tailscale serve가 host port를 메시 전용 HTTPS로 노출",
                    "재생성 내성 — init.sh가 매 부팅마다 의존성·심볼릭·sed 패치 재적용",
                    "수동 1회 — Hermes OAuth 인증만 사용자가 직접, 나머지는 자동",
                ],
                components=[
                    ("Tailscale", "host 데몬 — https://&lt;host&gt;.&lt;tailnet&gt;.ts.net 발급 + serve가 컨테이너 host port에 proxy"),
                    ("Paperclip", "원클릭 컨테이너 — init.sh가 python3·tini 설치, hermes 심볼릭, adapter sed 패치 후 /entrypoint.sh 위임"),
                    ("Hermes + Codex", "data/tools/opt-hermes(read-only bind mount)에서 venv 사용. Codex CLI v0.130은 paperclip 이미지에 이미 번들됨"),
                ],
            ),
            figure_block(
                "https://storage.googleapis.com/dante-labs-pub/tutorial/paperclip-hermes-codex/01-1-integrated-architecture-chalkboard.png",
                "통합 구조 한눈에 보기 — Tailscale 데몬 → Paperclip 컨테이너(init.sh 4단계) → Hermes + Codex (Dante Labs Chalkboard 테마)",
            ),
            table(
                rows=[
                    ("Hostinger VPS", "KVM 2 (RAM 2GB) 이상 권장 — Paperclip + Hermes 합산 ~1.5GB"),
                    ("Hostinger hPanel 계정", "원클릭 Paperclip 설치용"),
                    ("Tailscale 계정", "reusable auth key 발급 — https://login.tailscale.com/admin/settings/keys"),
                    ("ChatGPT Plus/Pro", "또는 Codex API 키 — Hermes openai-codex provider 인증"),
                    ("로컬 SSH 별칭", "~/.ssh/config 에 VPS 호스트 alias"),
                ],
                headers=("필요 항목", "비고"),
            ),
            check_block(
                "01-3. 확인 기준",
                "VPS에 SSH 접속이 가능하고 Hostinger hPanel · Tailscale admin · ChatGPT 계정 3개에 모두 로그인할 수 있습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "02",
        "title": "Hostinger 원클릭 Paperclip 설치",
        "lede": "hPanel의 Application templates에서 Paperclip을 선택하면 paperclipai 컨테이너가 Docker Manager에 자동 등록됩니다.",
        "blocks": [
            note_block(
                "02-1. hPanel 설치 절차",
                "hPanel → <strong>VPS</strong> → 대상 VPS → <strong>OS &amp; Panel → Operating System → Change OS</strong>를 클릭합니다. "
                "<strong>Application templates</strong> 카테고리에서 <strong>Paperclip</strong>을 선택하고 Install을 누릅니다. "
                "설치 마법사에서 Admin name(예: <code>Dante</code>), Email, 강한 32자 Password를 입력하고 API key 필드는 비워둡니다 (Hermes OAuth로 별도 인증).",
            ),
            code_block(
                "02-2. 설치 결과 검증",
                """\
ssh root@<vps-ip>

# 컨테이너 + Docker Manager 프로젝트 확인
docker ps --format "{{.Names}}: {{.State}}" | grep paperclip
ls /docker/paperclip-*/
cat /docker/paperclip-*/.env | grep -E "ADMIN|TRAEFIK\"""",
                "bash",
            ),
            note_block(
                "02-3. 컨테이너 이름 표기 규칙",
                "Hostinger가 만든 컨테이너 이름은 <code>paperclip-&lt;random&gt;-paperclip-1</code> 형태입니다. "
                "본 가이드는 <code>paperclip-kckc-paperclip-1</code> 형태로 표기하며, 실제 명령 실행 시 본인 환경의 random 부분으로 치환합니다. "
                "기본 노출은 Traefik HTTPS(<code>http://paperclip-&lt;random&gt;.&lt;vps-hostname&gt;.hstgr.cloud</code>)이며 STEP 05에서 Tailscale 노출로 교체합니다.",
            ),
            figure_block("02-hpanel-install.png", "hPanel Application templates — Paperclip 설치 마법사"),
            check_block(
                "02-4. 확인 기준",
                "<code>docker ps</code> 출력에 <code>paperclip-&lt;random&gt;-paperclip-1: running</code>이 표시되고, "
                "<code>/docker/paperclip-&lt;random&gt;/.env</code>에 <code>ADMIN_EMAIL</code>·<code>ADMIN_PASSWORD</code>·<code>TRAEFIK_HOST</code>가 채워져 있습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "03",
        "title": "Tailscale 설치 + VPS 인증 (host-level)",
        "lede": "VPS host에 Tailscale 데몬을 띄워 메시에 가입시킵니다. 이후 모든 외부 접근은 <code>&lt;hostname&gt;.&lt;tailnet&gt;.ts.net</code> URL을 사용합니다.",
        "blocks": [
            note_block(
                "03-1. Tailscale auth key 발급",
                "<a href=\"https://login.tailscale.com\">login.tailscale.com</a>에 가입(Google/Microsoft/GitHub OAuth 또는 이메일)하고 "
                "좌측 <strong>Settings → Keys → Generate auth key</strong>를 클릭합니다. "
                "옵션은 <strong>Reusable ✓</strong>, <strong>Expiration 90 days</strong>, Tags는 선택입니다 (예: <code>tag:paperclip</code>). "
                "생성된 <code>tskey-auth-...</code>는 1회만 표시되므로 즉시 복사합니다.",
            ),
            code_block(
                "03-2. VPS에 Tailscale 설치 + 인증",
                """\
ssh root@<vps-ip>
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled

# 위에서 복사한 auth key 사용
tailscale up --authkey=tskey-auth-<TS_AUTHKEY> \\
  --hostname=paperclip-hostinger --ssh

# 본 VPS의 tailnet FQDN 확보
tailscale status --peers=false --json \\
  | jq -r '.Self.DNSName' | sed 's/\\.$//'""",
                "bash",
            ),
            note_block(
                "03-3. 출력으로 받는 FQDN 형식",
                "<code>paperclip-hostinger.tail7b1307.ts.net</code> 형식입니다. "
                "앞부분은 <code>--hostname</code> 값이고 <code>tail7b1307</code>은 계정마다 다른 tailnet 식별자(Tailscale admin → DNS → Tailnet name에서 확인). "
                "이 FQDN을 이후 모든 단계에서 사용합니다.",
            ),
            check_block(
                "03-4. 확인 기준",
                "<code>tailscale status</code>에 <code>paperclip-hostinger</code>가 100.x.x.x로 표시되고 "
                "<code>--peers=false</code> 출력의 DNSName이 <code>&lt;hostname&gt;.&lt;tailnet&gt;.ts.net</code>으로 끝납니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "04",
        "title": "본인 디바이스에 Tailscale 클라이언트 설치 + 접속 검증",
        "lede": "브라우저로 <code>https://&lt;hostname&gt;.&lt;tailnet&gt;.ts.net/</code>에 접속하려면 본인 노트북·휴대폰도 같은 tailnet 멤버여야 합니다.",
        "blocks": [
            table(
                rows=[
                    ("macOS", "<a href=\"https://tailscale.com/download/mac\">tailscale.com/download/mac</a> — App Store 또는 .pkg 설치"),
                    ("Windows", "<a href=\"https://tailscale.com/download/windows\">tailscale.com/download/windows</a>"),
                    ("iOS", "App Store에서 'Tailscale' 검색"),
                    ("Android", "Play Store에서 'Tailscale' 검색"),
                    ("Linux", "<code>curl -fsSL https://tailscale.com/install.sh | sh &amp;&amp; tailscale up</code>"),
                ],
                headers=("OS", "설치"),
            ),
            note_block(
                "04-1. 로그인 후 확인",
                "설치 후 STEP 03에서 사용한 동일 Tailscale 계정으로 로그인합니다. "
                "macOS 메뉴바·Windows 트레이의 Tailscale 아이콘이 초록색이면 연결된 상태입니다.",
            ),
            code_block(
                "04-2. 본인 노트북에서 3종 검증",
                """\
# 1) Tailscale이 VPS를 peer로 인식하는지
tailscale status | grep paperclip-hostinger
# → 100.x.x.x  paperclip-hostinger  ...

# 2) 호스트네임이 100.x로 resolve되는지
ping -c 1 paperclip-hostinger.tail7b1307.ts.net
# → 100.120.195.40 응답

# 3) HTTPS Magic cert가 잡히는지 (paperclip 미노출이면 connection refused 정상)
curl -I https://paperclip-hostinger.tail7b1307.ts.net/""",
                "bash",
            ),
            note_block(
                "04-3. IP:port 직접 접근 차단",
                "<code>http://&lt;vps-ip&gt;:54748/</code> 형식은 Paperclip better-auth가 차단해 로그인 시도 시 401/403이 발생합니다 (Troubleshooting T9). "
                "반드시 <code>https://&lt;hostname&gt;.&lt;tailnet&gt;.ts.net/</code>를 사용합니다.",
            ),
            check_block(
                "04-4. 확인 기준",
                "3개 검증 모두 응답이 정상입니다. <code>tailscale status</code>에 peer가 보이고, "
                "ping이 100.x.x.x를 반환하며, curl이 connection refused(정상) 또는 응답을 받습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "05",
        "title": "Tailscale serve + PAPERCLIP_PUBLIC_URL 갱신",
        "lede": "Paperclip의 random host port를 Tailscale 443으로 매핑하고, compose의 hardcoded PUBLIC_URL을 <code>.env</code> override 가능한 형태로 패치합니다.",
        "blocks": [
            code_block(
                "05-1. Tailscale 443 → Paperclip host port",
                """\
# Paperclip 컨테이너의 host port 확인
docker port paperclip-kckc-paperclip-1
# 3100/tcp -> 0.0.0.0:54748

# Tailscale serve로 https 443 매핑
tailscale serve --bg --https=443 http://127.0.0.1:54748
tailscale serve status

# 기대 출력
# https://paperclip-hostinger.tail7b1307.ts.net (tailnet only)
# |-- / proxy http://127.0.0.1:54748""",
                "bash",
            ),
            code_block(
                "05-2. compose env 패치 — .env override 활성화",
                """\
cd /docker/paperclip-<random>/

# compose의 hardcoded PUBLIC_URL을 ${VAR:-default} 형태로 변환
sed -i.bak \\
  -e 's|PAPERCLIP_PUBLIC_URL: http://${COMPOSE_PROJECT_NAME}.${TRAEFIK_HOST}|PAPERCLIP_PUBLIC_URL: ${PAPERCLIP_PUBLIC_URL:-http://${COMPOSE_PROJECT_NAME}.${TRAEFIK_HOST}}|' \\
  -e 's|PAPERCLIP_ALLOWED_HOSTNAMES: ${TRAEFIK_HOST},${VPS_IP}:${PUBLIC_PORT}|PAPERCLIP_ALLOWED_HOSTNAMES: ${PAPERCLIP_ALLOWED_HOSTNAMES:-${TRAEFIK_HOST},${VPS_IP}:${PUBLIC_PORT}}|' \\
  docker-compose.yml
rm -f docker-compose.yml.bak""",
                "bash",
            ),
            code_block(
                "05-3. .env에 Tailscale FQDN 추가",
                """\
cat >> .env <<EOF
PAPERCLIP_PUBLIC_URL=https://paperclip-hostinger.tail7b1307.ts.net
PAPERCLIP_ALLOWED_HOSTNAMES=paperclip-hostinger.tail7b1307.ts.net,srv1431426.hstgr.cloud,156.67.219.3:54748
EOF""",
                "bash",
            ),
            note_block(
                "05-4. 값 치환",
                "<code>srv1431426</code>·IP 부분은 본인 VPS 값으로 치환합니다. <code>hostname -f</code> 또는 hPanel의 VPS 상세에서 확인할 수 있습니다.",
            ),
            check_block(
                "05-5. 확인 기준",
                "<code>tailscale serve status</code> 출력에 paperclip host port로 proxy 라인이 표시됩니다. "
                "<code>.env</code> 마지막 두 줄에 Tailscale FQDN 기반 URL이 들어가 있습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "06",
        "title": "Hermes·ttyd binary 추출 (1회)",
        "lede": "hermes-agent 공식 이미지에서 venv와 ttyd 바이너리를 꺼내 host의 <code>./data/tools/</code>로 옮깁니다. 이후 read-only bind mount로 컨테이너 안에 노출합니다.",
        "blocks": [
            code_block(
                "06-1. tmp 컨테이너로 binary 추출",
                """\
mkdir -p /docker/paperclip-<random>/data/tools

docker create --name tmp-hermes ghcr.io/hostinger/hvps-hermes-agent:latest
docker cp tmp-hermes:/opt/hermes /docker/paperclip-<random>/data/tools/opt-hermes
docker cp tmp-hermes:/usr/bin/ttyd /docker/paperclip-<random>/data/tools/ttyd
docker rm tmp-hermes""",
                "bash",
            ),
            note_block(
                "06-2. 디스크 사용량",
                "<code>data/tools/opt-hermes</code>는 Python venv 포함해 약 1.9GB를 차지합니다. "
                "이미지를 매 부팅마다 다시 pull하지 않고 host bind mount로 사용하면 컨테이너 재생성에도 영향받지 않습니다.",
            ),
            check_block(
                "06-3. 확인 기준",
                "<code>ls /docker/paperclip-&lt;random&gt;/data/tools/</code>에 <code>opt-hermes/</code> 디렉터리와 <code>ttyd</code> 파일이 보입니다. "
                "<code>du -sh data/tools/opt-hermes</code>가 1.5~2.0GB 범위입니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "07",
        "title": "docker-compose 확장 + init 스크립트",
        "lede": "매 부팅마다 root 권한으로 의존성을 보충하고 hermes 심볼릭과 adapter 패치를 적용하는 idempotent init.sh를 만들고 compose에 mount합니다.",
        "blocks": [
            code_block(
                "07-1. init.sh 작성 (호스트 영구 파일)",
                """\
cat > /docker/paperclip-<random>/data/tools/init.sh <<'BASH'
#!/bin/bash
set -e

# 1) Install python3 + tini if absent (Debian 13 base lacks them)
if ! command -v python3 >/dev/null 2>&1 || ! command -v tini >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3 tini
fi

# 2) Symlink hermes binary to default PATH
sudo ln -sf /opt/hermes/.venv/bin/hermes /usr/local/bin/hermes

# 3) Apply hermes-paperclip-adapter PR #123 patch (drop DEFAULT_MODEL fallback)
ADAPTER_JS=/usr/local/lib/node_modules/paperclipai/node_modules/hermes-paperclip-adapter/dist/server/execute.js
if [ -f "$ADAPTER_JS" ] && grep -q "cfgString(config.model) || DEFAULT_MODEL" "$ADAPTER_JS" 2>/dev/null; then
  sudo sed -i "s#cfgString(config.model) || DEFAULT_MODEL#cfgString(config.model)#g" "$ADAPTER_JS"
fi

# 4) Hand off to original paperclip entrypoint
exec bash -c /entrypoint.sh
BASH
chmod +x /docker/paperclip-<random>/data/tools/init.sh""",
                "bash",
            ),
            code_block(
                "07-2. docker-compose.yml — entrypoint + mount 주입",
                """\
# paperclip 서비스의 volumes 직전에 entrypoint 라인 + 마운트 4종 삽입
    entrypoint: ["bash", "/paperclip-tools/init.sh"]
    volumes:
      - ./data:/paperclip
      - ./data/tools:/paperclip-tools:ro
      - ./data/tools/opt-hermes:/opt/hermes:ro
      - ./data/tools/ttyd:/usr/local/bin/ttyd:ro""",
                "yaml",
            ),
            note_block(
                "07-3. node 사용자 sudo 권한",
                "Paperclip 이미지는 node user에게 NOPASSWD sudo를 부여합니다. "
                "init.sh의 <code>sudo apt-get install</code>·<code>sudo ln -sf</code>·<code>sudo sed</code>가 비밀번호 없이 실행됩니다.",
            ),
            check_block(
                "07-4. 확인 기준",
                "<code>data/tools/init.sh</code>가 실행 권한(<code>chmod +x</code>)을 갖고 있고, "
                "<code>docker-compose.yml</code>의 paperclip 서비스 블록에 <code>entrypoint: [\"bash\", \"/paperclip-tools/init.sh\"]</code> 라인과 마운트 4종이 추가되어 있습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "08",
        "title": "컨테이너 재시작 + 검증",
        "lede": "force-recreate로 컨테이너를 새 entrypoint와 함께 띄우고 init.sh가 정상 적용됐는지 6종 검증을 수행합니다.",
        "blocks": [
            code_block(
                "08-1. force-recreate",
                """\
cd /docker/paperclip-<random>/
docker compose up -d --force-recreate

# 약 30초 대기
sleep 30""",
                "bash",
            ),
            code_block(
                "08-2. 6종 검증 명령",
                """\
docker exec paperclip-<random>-paperclip-1 sh -c '
  echo --- python3, tini, hermes, ttyd ---
  command -v python3 tini hermes ttyd
  hermes --version

  echo --- adapter patch ---
  grep -c "cfgString(config.model) || DEFAULT_MODEL" \\
    /usr/local/lib/node_modules/paperclipai/node_modules/hermes-paperclip-adapter/dist/server/execute.js

  echo --- paperclip health ---
  curl -sf http://127.0.0.1:3100/api/health
'
docker logs --tail 20 paperclip-<random>-paperclip-1 2>&1 | grep -i "authPublicBaseUrl\"""",
                "bash",
            ),
            note_block(
                "08-3. 기대 결과",
                "<code>python3, tini, hermes, ttyd</code> 모두 path resolve가 되고 <code>hermes --version</code>이 정상 응답합니다. "
                "<code>adapter patch</code>의 grep 카운트는 <strong>0</strong>(이미 패치됨)입니다. "
                "<code>/api/health</code>가 <code>{\"status\":\"ok\",\"bootstrapStatus\":\"ready\"}</code>를 반환합니다. "
                "로그의 <code>authPublicBaseUrl</code>이 <code>https://&lt;host&gt;.&lt;tailnet&gt;.ts.net</code>입니다.",
            ),
            check_block(
                "08-4. 확인 기준",
                "6종 검증 모두 통과합니다. 한 가지라도 실패하면 Troubleshooting T2(hermes), T4(apt), T5(entrypoint), T6(PUBLIC_URL)을 차례로 확인합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "09",
        "title": "Hermes OAuth 인증 (수동, 1회)",
        "lede": "ChatGPT 계정 OAuth 토큰을 Hermes의 openai-codex provider에 등록합니다. <code>--user node</code>를 빼먹지 않습니다.",
        "blocks": [
            code_block(
                "09-1. device-auth 시작",
                """\
docker exec -it --user node paperclip-<random>-paperclip-1 \\
  hermes auth add openai-codex --type oauth --no-browser""",
                "bash",
            ),
            note_block(
                "09-2. 표시되는 URL + 1회용 코드",
                "출력 예: <code>https://auth.openai.com/codex/device</code> + <code>6SYR-QWB3Z</code>. "
                "URL을 브라우저에서 열고 ChatGPT 계정으로 로그인한 다음 코드를 입력합니다. "
                "코드는 15분 안에 사용해야 하며 만료되면 같은 명령을 다시 실행하면 새 코드가 발급됩니다.",
            ),
            code_block(
                "09-3. 인증 결과 검증",
                """\
docker exec --user node paperclip-<random>-paperclip-1 \\
  hermes auth status openai-codex

# 기대 출력
# openai-codex: logged in""",
                "bash",
            ),
            note_block(
                "09-4. --user node가 필수인 이유",
                "auth.json은 <code>/home/node/.hermes/auth.json</code>에 저장됩니다. "
                "<code>--user node</code> 없이 실행하면 root HOME(<code>/paperclip</code>)을 사용해 인증한 토큰을 다른 명령에서 찾지 못합니다 (Troubleshooting T3).",
            ),
            check_block(
                "09-5. 확인 기준",
                "<code>hermes auth status openai-codex</code> 출력이 <code>logged in</code>이고 "
                "<code>docker exec --user node ... ls /home/node/.hermes/auth.json</code>이 파일을 보여줍니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "10",
        "title": "Hermes 모델·프로바이더 설정",
        "lede": "OAuth만으로는 부족합니다. Hermes config에 default model을 명시해야 paperclip의 detect-model이 정상 작동합니다.",
        "blocks": [
            code_block(
                "10-1. config 3줄 + 검증",
                """\
docker exec --user node paperclip-<random>-paperclip-1 bash -c '
  hermes config set model.provider openai-codex
  hermes config set model.default gpt-5.5
  hermes config set model.base_url https://chatgpt.com/backend-api/codex

  echo --- verify ---
  hermes status | grep -E "Model|Provider"
'""",
                "bash",
            ),
            note_block(
                "10-2. 기대 출력",
                "<code>Model:        gpt-5.5</code><br><code>Provider:     OpenAI Codex</code>. "
                "이 두 줄이 정확히 나오지 않으면 Paperclip의 어댑터가 <em>Hermes isn't configured yet</em> 오류를 던집니다 (Troubleshooting T8).",
            ),
            check_block(
                "10-3. 확인 기준",
                "<code>hermes status</code>의 Model과 Provider 라인이 모두 채워져 있습니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "11",
        "title": "Paperclip Company + CEO 에이전트 생성",
        "lede": "Tailscale FQDN URL로 Paperclip UI에 로그인해 회사와 첫 CEO 에이전트를 만듭니다.",
        "blocks": [
            note_block(
                "11-1. 브라우저 절차",
                "본인 노트북에서 Tailscale 클라이언트가 켜진 상태로 (STEP 04 완료) "
                "<code>https://paperclip-hostinger.tail7b1307.ts.net/</code>에 접속합니다. "
                "Sign-in 화면에서 STEP 02의 admin 이메일·비밀번호로 로그인합니다. "
                "상단 <strong>Create company</strong>로 회사명을 입력해 생성하고, "
                "좌측 nav → <strong>Agents → Create agent</strong>를 클릭합니다.",
            ),
            table(
                rows=[
                    ("Name", "<code>CEO</code>"),
                    ("Role", "<code>ceo</code>"),
                    ("Adapter", "<strong>Hermes Agent</strong>"),
                    ("Model", "비워둠 — Hermes config의 default(gpt-5.5) 자동 사용"),
                    ("Provider", "비워둠 — <code>openai-codex</code> 자동"),
                    ("Timeout (seconds)", "<code>900</code> — gpt-5.5 thinking phase가 300초보다 길 수 있음"),
                    ("Effort / Reasoning", "<code>medium</code>"),
                ],
                headers=("필드", "값"),
            ),
            code_block(
                "11-2. API path (스크립트화)",
                """\
# 11-2-1. paperclip login → cookie
ADMIN_PW=$(grep ADMIN_PASSWORD /docker/paperclip-<random>/.env | cut -d= -f2)

docker exec paperclip-<random>-paperclip-1 sh -c "
curl -sS -c /tmp/cookies.txt -b /tmp/cookies.txt \\
  -H 'Content-Type: application/json' \\
  -H 'Origin: https://<host>.<tailnet>.ts.net' \\
  -X POST http://localhost:3100/api/auth/sign-in/email \\
  --data '{\\"email\\":\\"you@example.com\\",\\"password\\":\\"$ADMIN_PW\\"}'
"

# 11-2-2. company create
CID=$(docker exec paperclip-<random>-paperclip-1 sh -c '
  curl -sS -b /tmp/cookies.txt -H "Content-Type: application/json" -H "Origin: https://<host>.<tailnet>.ts.net" \\
    -X POST http://localhost:3100/api/companies \\
    --data "{\\"name\\":\\"DanteLabs\\"}"
' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "company id: $CID"

# 11-2-3. CEO agent
docker exec paperclip-<random>-paperclip-1 sh -c "
curl -sS -b /tmp/cookies.txt -H 'Content-Type: application/json' -H 'Origin: https://<host>.<tailnet>.ts.net' \\
  -X POST http://localhost:3100/api/companies/$CID/agents \\
  --data '{
    \\"name\\":\\"CEO\\",
    \\"role\\":\\"ceo\\",
    \\"title\\":\\"Chief Executive Officer\\",
    \\"adapterType\\":\\"hermes_local\\",
    \\"adapterConfig\\":{\\"timeoutSec\\":900,\\"effort\\":\\"medium\\",\\"persistSession\\":true},
    \\"capabilities\\":\\"전사 전략 결정, 다중 에이전트 오케스트레이션\\"
  }'
\"""",
                "bash",
            ),
            note_block(
                "11-3. model·provider를 비워두는 이유",
                "STEP 07 init.sh가 적용한 어댑터 sed 패치 덕분에 <code>adapterConfig.model</code>이 비면 Hermes config의 default(<code>gpt-5.5</code>/<code>openai-codex</code>)를 사용합니다. "
                "값을 명시하면 어댑터의 inline override가 적용되어 의도와 다르게 동작할 수 있습니다.",
            ),
            check_block(
                "11-4. 확인 기준",
                "Paperclip UI의 Agents 목록에 CEO 에이전트가 표시되고 상세 페이지에서 <code>adapterType: hermes_local</code>·<code>timeoutSec: 900</code>이 확인됩니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "12",
        "title": "Persona(AGENTS.md) 작성",
        "lede": "CEO 에이전트의 system prompt를 명시해 응답 톤과 책임 범위를 고정합니다.",
        "blocks": [
            code_block(
                "12-1. persona 본문 작성 (호스트)",
                """\
AGENT_ID=<STEP 11에서 받은 CEO id>

cat > /tmp/persona.md <<'PERSONA'
# 정체성

당신은 Dante Labs의 CEO입니다. AI·데이터 비즈니스 의사결정과 다중 Hermes 에이전트 조직 운영을 책임집니다. 기본 응답 언어는 한국어이며, 글로벌 컨텍스트(영문 자료·표기)는 자연스럽게 병기합니다.

# 책임

1. **전략 결정** — 회사 단기·장기 목표와 진행 중인 프로젝트의 우선순위 결정.
2. **에이전트 오케스트레이션** — 새 이슈가 들어오면 적절한 전문가 에이전트를 hire하거나 기존 에이전트에 위임.
3. **산출물 리뷰** — 각 에이전트의 결과 검토 + 후속 태스크 분배.
4. **보고·요약** — 결정 사유 + 다음 단계 권장 + 리소스 영향(시간·비용·리스크) 함께 명시.

# 운영 원칙

- "왜"와 "다음 행동"을 항상 함께.
- 출처·근거 표기. 추측은 "추측"으로 명시.
- Trade-off(빠름 vs 정확, 비용 vs 품질)를 결정 사유에 포함.
- 보안·컴플라이언스 영향 있는 결정은 별도 코멘트로 강조.
- 본인은 의사결정·위임·리뷰만. 코드/분석은 전문가 에이전트에게 위임.

# 응답 톤

- 간결, 단호, 사실 기반.
- 모르는 영역은 누구에게 위임할지 명시.
PERSONA""",
                "bash",
            ),
            code_block(
                "12-2. 컨테이너로 복사 + PUT",
                """\
docker cp /tmp/persona.md paperclip-<random>-paperclip-1:/tmp/persona.md

docker exec paperclip-<random>-paperclip-1 bash -c '
  python3 -c "import json,sys; print(json.dumps({\\"path\\":\\"AGENTS.md\\",\\"content\\":open(\\"/tmp/persona.md\\").read()}))" > /tmp/p.json
  curl -sS -b /tmp/cookies.txt -X PUT \\
    -H "Content-Type: application/json" -H "Origin: https://<host>.<tailnet>.ts.net" \\
    --data @/tmp/p.json \\
    http://localhost:3100/api/agents/'"$AGENT_ID"'/instructions-bundle/file
'""",
                "bash",
            ),
            note_block(
                "12-3. UI 대체 경로",
                "Paperclip UI에서 agent 상세 → <strong>Instructions</strong> 섹션의 markdown editor에서 직접 편집해도 동일한 효과입니다.",
            ),
            check_block(
                "12-4. 확인 기준",
                "Paperclip UI의 agent → Instructions 탭에서 작성한 persona가 그대로 표시됩니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "13",
        "title": "가벼운 태스크로 체인 검증",
        "lede": "간단한 issue를 만들어 Paperclip → Hermes → Codex → ChatGPT 전체 체인이 응답하는지 확인합니다.",
        "blocks": [
            code_block(
                "13-1. issue 생성",
                """\
CID=<STEP 11 company id>
AGENT_ID=<STEP 11 CEO id>

docker exec paperclip-<random>-paperclip-1 sh -c "
curl -sS -b /tmp/cookies.txt -X POST \\
  -H 'Content-Type: application/json' -H 'Origin: https://<host>.<tailnet>.ts.net' \\
  --data '{
    \\"title\\":\\"GDP 약자 확인\\",
    \\"body\\":\\"GDP의 영문 풀네임을 한 문장으로 답하세요.\\",
    \\"status\\":\\"todo\\",
    \\"assigneeAgentId\\":\\"$AGENT_ID\\"
  }' \\
  http://localhost:3100/api/companies/$CID/issues
\"""",
                "bash",
            ),
            note_block(
                "13-2. 기대 동작",
                "Paperclip UI에서 새 issue가 약 1.5분 후 <strong>done</strong> 상태로 전환되고 코멘트에 "
                "<em>'GDP는 Gross Domestic Product의 약자이며, 한국어로는 국내총생산입니다.'</em> 같은 답변이 달립니다.",
            ),
            code_block(
                "13-3. CLI로 run log 추적",
                """\
ISS=<issue id>

docker exec paperclip-<random>-paperclip-1 bash -c "
  RID=\\$(curl -s -b /tmp/cookies.txt http://localhost:3100/api/issues/$ISS/runs \\
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d if isinstance(d,list) else d[\\"runs\\"])[0][\\"runId\\"])')
  curl -s -b /tmp/cookies.txt http://localhost:3100/api/heartbeat-runs/\\$RID/log \\
    | python3 -c 'import sys,json; print(json.load(sys.stdin)[\\"content\\"][:2000])'
\"""",
                "bash",
            ),
            note_block(
                "13-4. 기대 로그 라인",
                "<code>[hermes] Starting Hermes Agent (model=undefined, provider=auto [auto], timeout=900s)</code> + "
                "<code>[hermes] Exit code: 0, timed out: false</code>. "
                "<code>model=undefined</code>는 어댑터 sed 패치가 정상 적용된 신호이며, 실제 모델은 Hermes config default(gpt-5.5)를 사용합니다.",
            ),
            check_block(
                "13-5. 확인 기준",
                "issue가 done 상태로 전환되고 코멘트에 모델 답변이 있습니다. <code>Exit code: 0, timed out: false</code>가 로그 마지막에 나타납니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "14",
        "title": "Hermes Dashboard·ttyd 노출 (선택)",
        "lede": "Paperclip UI 외에 Hermes Dashboard와 브라우저 터미널(ttyd)을 추가로 쓰고 싶을 때만 적용합니다.",
        "blocks": [
            code_block(
                "14-1. 컨테이너 안 background spawn",
                """\
docker exec -d --user node paperclip-<random>-paperclip-1 bash -c '
  hermes dashboard --port 9119 --host 0.0.0.0 --insecure --no-open --skip-build
'

ADMIN_USERNAME=dante
ADMIN_PASSWORD=$(grep ADMIN_PASSWORD /docker/paperclip-<random>/.env | cut -d= -f2)
docker exec -d --user node paperclip-<random>-paperclip-1 bash -c "
  ttyd -p 4860 -W -c \\"$ADMIN_USERNAME:$ADMIN_PASSWORD\\" hermes
\"""",
                "bash",
            ),
            code_block(
                "14-2. compose에 포트 추가 (영구화)",
                """\
    ports:
      - "${PUBLIC_PORT}:3100"
      - "9119:9119"
      - "4860:4860\"""",
                "yaml",
            ),
            code_block(
                "14-3. Tailscale serve로 추가 매핑",
                """\
tailscale serve --bg --https=9119 http://127.0.0.1:9119
tailscale serve --bg --https=4860 http://127.0.0.1:4860
tailscale serve status""",
                "bash",
            ),
            note_block(
                "14-4. 접속 URL",
                "<code>https://&lt;host&gt;.&lt;tailnet&gt;.ts.net:9119</code> → Hermes Dashboard. "
                "<code>https://&lt;host&gt;.&lt;tailnet&gt;.ts.net:4860</code> → ttyd basic-auth (ADMIN_USERNAME / ADMIN_PASSWORD).",
            ),
            check_block(
                "14-5. 확인 기준",
                "두 URL 모두 정상 로딩되고 ttyd는 basic-auth 후 컨테이너 안 hermes 쉘에 접속됩니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "15",
        "title": "Troubleshooting — 10개 함정과 해결책",
        "lede": "실제 시뮬레이션에서 마주친 순서대로 정리한 10개 함정. 증상을 확인한 다음 해당 STEP의 fix를 적용합니다.",
        "blocks": [
            note_block(
                "T1. Hostinger 콘솔 Terminal 버튼이 'No such container'",
                "<strong>원인</strong> — hPanel의 컨테이너 카드 Terminal 버튼은 페이지 로드 시점의 컨테이너 ID를 캐시합니다. "
                "<code>docker compose up -d --force-recreate</code> 후 ID가 바뀌면 stale link가 됩니다.<br>"
                "<strong>해결</strong> — 콘솔 페이지를 새로고침해서 새 ID로 Terminal을 다시 엽니다. 또는 SSH로 <code>docker exec -it --user node &lt;name&gt; bash</code>를 직접 실행합니다.",
            ),
            note_block(
                "T2. <code>hermes: command not found</code> in container terminal",
                "<strong>원인</strong> — hermes 바이너리는 <code>/opt/hermes/.venv/bin/hermes</code>에 있고 기본 PATH에 노출되지 않습니다.<br>"
                "<strong>해결</strong> — STEP 07 init.sh의 <code>ln -sf /opt/hermes/.venv/bin/hermes /usr/local/bin/hermes</code> 라인이 매 부팅마다 적용됩니다. 컨테이너 재시작 후 아무 위치에서나 <code>hermes</code> 호출이 됩니다.",
            ),
            note_block(
                "T3. <code>hermes auth status</code> → logged out인데 토큰은 있음",
                "<strong>원인</strong> — 컨테이너 기본 HOME이 <code>/paperclip</code>인데 auth.json은 <code>/home/node/.hermes/auth.json</code>에 저장됩니다.<br>"
                "<strong>해결</strong> — 모든 hermes 명령은 <code>docker exec --user node ...</code>로 invoke합니다. node user의 /etc/passwd home인 <code>/home/node</code>가 자동 적용됩니다.",
            ),
            note_block(
                "T4. <code>apt-get install</code>: Permission denied",
                "<strong>원인</strong> — paperclip 이미지의 ENTRYPOINT는 node user로 실행되며 node는 <code>/var/lib/apt</code>에 쓰기 권한이 없습니다.<br>"
                "<strong>해결</strong> — paperclip 이미지는 node user에 NOPASSWD sudo를 부여합니다. init.sh의 <code>sudo apt-get install ...</code>이 비밀번호 없이 통과합니다.",
            ),
            note_block(
                "T5. paperclip restart loop: <code>/entrypoint: No such file or directory</code>",
                "<strong>원인</strong> — paperclip 이미지의 entrypoint는 <code>bash -c \"/entrypoint.sh\"</code>(<code>.sh</code> 확장자 필수)입니다. custom wrapper에서 <code>/entrypoint</code>(확장자 없이)로 호출하면 ENOENT가 발생합니다.<br>"
                "<strong>해결</strong> — STEP 07 init.sh의 마지막 라인을 <code>exec bash -c /entrypoint.sh</code>로 작성합니다.",
            ),
            note_block(
                "T6. <code>PAPERCLIP_PUBLIC_URL</code>이 .env를 update해도 그대로",
                "<strong>원인</strong> — Hostinger 기본 <code>docker-compose.yml</code>의 environment 섹션이 <code>http://${COMPOSE_PROJECT_NAME}.${TRAEFIK_HOST}</code>로 hardcode되어 .env override를 무시합니다.<br>"
                "<strong>해결</strong> — STEP 05의 sed 패치로 <code>${PAPERCLIP_PUBLIC_URL:-...}</code> 형태로 바꿉니다. 이후 .env 변경이 컨테이너 환경에 반영됩니다.",
            ),
            note_block(
                "T7. Hermes adapter spawns <code>model=anthropic/claude-sonnet-4</code>",
                "<strong>원인</strong> — <code>hermes-paperclip-adapter</code> v0.2.1의 <code>DEFAULT_MODEL</code> fallback 버그. <code>agent.adapterConfig.model</code>이 비면 anthropic으로 fallback합니다.<br>"
                "<strong>해결</strong> — STEP 07 init.sh의 sed가 hermes-paperclip-adapter PR #123(<em>Use Hermes profile defaults when model is unset</em>)을 mirror합니다. 패치 후 빈 model 값은 Hermes config의 default를 사용합니다.",
            ),
            note_block(
                "T8. Task: <code>Hermes isn't configured yet — no API keys or providers found</code>",
                "<strong>원인</strong> — OAuth만 등록하고 <code>hermes config set model.provider/model.default/model.base_url</code>을 실행하지 않은 상태입니다.<br>"
                "<strong>해결</strong> — STEP 10의 3줄 config set을 실행합니다. <code>hermes status</code>에서 Model과 Provider 라인이 정확히 나오는지 확인합니다.",
            ),
            note_block(
                "T9. <code>http://&lt;vps-ip&gt;:54748/</code> 접속 시 sign-in 후 401/403",
                "<strong>원인</strong> — Paperclip의 better-auth는 <code>PAPERCLIP_PUBLIC_URL</code> origin만 trusted로 처리합니다. STEP 05에서 그 값을 Tailscale FQDN으로 set했으므로 IP+port HTTP 접근은 cross-origin으로 차단됩니다.<br>"
                "<strong>해결</strong> — 본인 노트북에 Tailscale 클라이언트를 설치(STEP 04)하고 브라우저로 <code>https://&lt;hostname&gt;.&lt;tailnet&gt;.ts.net/</code>를 사용합니다. "
                "IP+port를 굳이 노출하려면 <code>.env</code>의 <code>PAPERCLIP_PUBLIC_URL</code>을 IP 형식으로 변경 후 <code>--force-recreate</code>합니다 (인터넷 전체 노출 권장 안 함).",
            ),
            note_block(
                "T10. <code>tailscale status</code>에 VPS는 보이는데 <code>https://...ts.net/</code>이 안 열림",
                "<strong>원인</strong> — 본인 디바이스의 Tailscale은 running이지만 DNS 옵션이 꺼져 있어 <code>.ts.net</code> 호스트네임이 OS resolver로 빠지지 않습니다.<br>"
                "<strong>해결</strong> — macOS는 Tailscale 메뉴바 아이콘 → Preferences → <strong>Use Tailscale DNS</strong>를 체크합니다. "
                "또는 100.x.x.x IP로 직접 접속하지만 magic cert가 hostname 기준이라 cert warning이 발생합니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "16",
        "title": "위임 프롬프트 (Codex CLI · Paperclip CEO)",
        "lede": "설치 자동화는 Codex CLI에 위임하고, 운영 중에는 Paperclip CEO 에이전트에 issue를 할당합니다.",
        "blocks": [
            code_block(
                "16-1. Codex CLI 진입",
                """\
# 대화형 — 컨테이너 안 codex REPL
docker exec -it --user node paperclip-<random>-paperclip-1 codex

# Non-interactive — workspace-write 모드로 single shot
codex exec --workspace-write -m gpt-5-codex 'YOUR_PROMPT'""",
                "bash",
            ),
            code_block(
                "16-2. Codex CLI 설치 자동화 프롬프트 (1회 복붙용)",
                """\
당신은 Hostinger VPS 위 Paperclip + Hermes + Codex 스택의 설치·운영 자동화 보조자입니다. 사용자는 manual-install 가이드를 따르고 있고, 당신은 그 가이드의 명령을 정확히 실행하여 사용자 부담을 줄입니다.

# 작업 원칙

1. 명령 전 컨텍스트 검증:
   - docker ps로 paperclip 컨테이너 이름 확인
   - cat /docker/<project>/.env로 ADMIN_PASSWORD/TRAEFIK_HOST/VPS_IP 확인
   - tailscale status --peers=false --json로 Tailscale FQDN 확인

2. destructive 작업은 사용자 확인: docker compose down -v, rm -rf data/, tailscale logout 등은 자동 실행하지 말고 명시적 승인 요청.

3. OAuth 단계는 사용자에게 위임: hermes auth add openai-codex 같은 device-flow는 device URL/code를 그대로 보고하고 인증 완료 대기.

4. 시크릿 마스킹: ADMIN_PASSWORD, TS_AUTHKEY, OPENAI_API_KEY, Codex/Hermes OAuth access_token은 첫 8자 + ***으로 마스킹.

5. 함정 회피:
   - docker exec에 항상 --user node
   - HOME은 /home/node여야 hermes가 auth.json 찾음
   - /entrypoint가 아니라 /entrypoint.sh
   - apt install은 sudo
   - .env 수정만으로 compose env가 안 바뀌면 docker-compose.yml의 environment 섹션이 hardcode — ${VAR:-default} 형태로 패치
   - hermes-paperclip-adapter v0.2.x는 DEFAULT_MODEL fallback bug — sed patch가 init.sh에 있어야 영구

6. 각 STEP 끝 검증:
   - paperclip /api/health → 200 ok
   - hermes auth status openai-codex → logged in
   - hermes status | grep -E "Model|Provider" → 정확
   - 어댑터 sed 패치: grep -c "cfgString(config.model) || DEFAULT_MODEL" 결과 0

# 임무

STEP 01부터 STEP 14까지 순서대로 진행. 각 STEP 시작 시 진행 의사 확인. STEP 끝마다 검증 결과를 한 줄로 요약. 에러 발생 시 T1~T10 매칭 후 fix 적용. 외 에러는 stack trace + 의심 원인 + 제안 fix 3가지로 보고.""",
                "text",
            ),
            code_block(
                "16-3. Paperclip CEO Issue 권장 형식",
                """\
title: <한 문장 명확한 요청>

body:
## 배경
<왜 이 task가 필요한지 1-3줄>

## 입력
<재료가 되는 데이터·문서·이전 결정 링크>

## 출력 형식
<원하는 답변 구조 — bullet, 표, 절차 등>

## 제약
- 시간: <urgency>
- 리소스: <비용·도구 제약>
- 보안: <외부 공유 여부>

## 위임 권장
<특정 전문가 agent 호출이 필요하면 여기에>""",
                "text",
            ),
            code_block(
                "16-4. CEO Issue 작동 예시 — Q4 OKR 초안",
                """\
title: Q4 OKR 초안 작성

body:
## 배경
4분기 시작. 회사 전략 일관성 + 팀 우선순위 정렬 필요.

## 입력
- Q3 OKR 결과: /docs/q3-okr-retro.md
- 진행 중 프로젝트 3개: Paperclip 스택, Hermes 가이드 v2, AI 강의 신규 모듈

## 출력 형식
- 핵심 목표 3개 (Objective)
- 각 목표마다 측정 가능한 Key Result 2~3개
- 책임자(역할명)와 1차 마감

## 제약
- 시간: 2시간 reasoning
- 보안: 외부 공유 안 함

## 위임 권장
- 시장 분석 데이터가 필요하면 'researcher' 호출
- 코드 작성/리뷰가 필요하면 'engineer' 호출
- CEO는 의사결정·우선순위 결정·리뷰만""",
                "text",
            ),
            check_block(
                "16-5. 확인 기준",
                "Codex CLI 진입 시 <code>codex&gt;</code> 프롬프트가 표시됩니다. "
                "Paperclip UI에서 CEO에 위 형식의 issue를 할당하면 STEP 13과 유사한 done 전환이 일어납니다.",
            ),
        ],
    },
    # ------------------------------------------------------------------
    {
        "num": "17",
        "title": "Hostinger Update 회복 + 함정 요약표",
        "lede": "hPanel Docker Manager의 Update 버튼이 일어나도 init.sh가 매 부팅마다 의존성을 재적용하므로 사용자 추가 작업이 필요 없습니다.",
        "blocks": [
            note_block(
                "17-1. Update 버튼이 일어나는 일",
                "Hostinger Update는 본질적으로 <code>docker compose pull &amp;&amp; docker compose up -d --force-recreate</code>입니다. "
                "1) paperclip 이미지의 새 :latest pull, "
                "2) 컨테이너 force-recreate, "
                "3) 컨테이너 안 변경(apt install·sed patch·심볼릭)은 사라짐, "
                "4) 그러나 host bind mount된 init.sh가 매 시작 시 자동 재적용 — 사용자 작업 없이 복구.",
            ),
            note_block(
                "17-2. 예외 — compose 자체가 reset되는 경우",
                "<code>docker-compose.yml</code> 자체가 Hostinger template으로 reset되면 STEP 05·07의 compose 수정(<code>PAPERCLIP_PUBLIC_URL:-...</code> 패치, entrypoint, mount 추가)이 사라집니다. "
                "그 경우 STEP 05·07을 다시 적용합니다. "
                "<code>/docker/paperclip-&lt;random&gt;/data/tools/</code> 디렉터리는 Hostinger update가 건드리지 않습니다 (data 마운트 영역).",
            ),
            note_block(
                "17-3. 안전한 영구화 단위",
                "가장 안전한 영구화 단위는 <strong>data/tools/ 디렉터리에 모든 보조 binary와 script를 두고, compose에는 그 디렉터리만 bind mount</strong>하는 형태입니다. "
                "이 가이드의 STEP 06·07이 그 패턴을 그대로 적용합니다.",
            ),
            table(
                rows=[
                    ("T1", "Console terminal stale ID", "hPanel UI 캐시", "페이지 새로고침"),
                    ("T2", "hermes command not found", "PATH 미노출", "init.sh 심볼릭"),
                    ("T3", "hermes auth status logged out", "HOME 차이", "--user node 명시"),
                    ("T4", "apt install Permission denied", "node not root", "init.sh sudo"),
                    ("T5", "restart loop /entrypoint ENOENT", "path typo", "bash -c /entrypoint.sh"),
                    ("T6", "PAPERCLIP_PUBLIC_URL 갱신 안 됨", "compose hard-coded env", "sed ${VAR:-...}"),
                    ("T7", "model=anthropic/claude-sonnet-4 spawn", "adapter v0.2.1 DEFAULT_MODEL fallback", "init.sh sed patch (mirror PR #123)"),
                    ("T8", "Hermes isn't configured", "hermes config 미설정", "hermes config set 3줄"),
                    ("T9", "IP:port 접속 시 401/403", "PAPERCLIP_PUBLIC_URL origin 불일치", "Tailscale FQDN 접속"),
                    ("T10", ".ts.net 도메인 안 열림", "Tailscale DNS 옵션 OFF", "Use Tailscale DNS 체크"),
                ],
                headers=("#", "증상", "원인", "해결 위치"),
            ),
            check_block(
                "17-4. 확인 기준",
                "Hostinger Update 버튼을 눌러도 컨테이너가 자동 재기동되고 STEP 08의 6종 검증이 모두 통과합니다. "
                "통과하지 못하면 T1~T10 순서대로 확인합니다.",
            ),
        ],
    },
]


# ---------------------------------------------------------------------------
# Body builder
# ---------------------------------------------------------------------------

def body() -> str:
    rendered = "\n".join(render_step(section) for section in SECTIONS)
    return f"""
<body>
  <header class="hero">
    <div class="hero-inner">
      <span class="eyebrow">Manual Install · Paperclip × Hermes × Codex on Hostinger</span>
      <h1>Paperclip + Hermes + Codex — Hostinger 원클릭 위에 수동 설치</h1>
      <p>호스팅어 hPanel의 원클릭 Paperclip 컨테이너 위에 Hermes Agent와 Codex CLI를 얹어 멀티 에이전트 오케스트레이션을 운영합니다. Tailscale 메시 전용 노출 + init.sh 자동 복구로 호스팅어 Update 버튼에도 영구.</p>
      <dl class="meta-grid">
        <div><dt>대상</dt><dd>Hostinger hPanel 원클릭 Paperclip 사용자</dd></div>
        <div><dt>모드</dt><dd>Tailscale 메시 전용 (외부 노출 0)</dd></div>
        <div><dt>컨테이너</dt><dd>1개 (paperclipai) + host Tailscale 데몬</dd></div>
        <div><dt>OAuth</dt><dd>Hermes · 사용자 1회 수동</dd></div>
        <div><dt>영구화</dt><dd>data/tools/ bind mount + init.sh</dd></div>
        <div><dt>마지막 검증</dt><dd>2026-05-18 (Paperclip onboarding flow)</dd></div>
      </dl>
    </div>
  </header>
  <main class="container">
    {rendered}
  </main>
  <footer>
    <p>원본 매뉴얼 · <a href="../manual-install-on-one-click-paperclip.md">docs/manual-install-on-one-click-paperclip.md</a></p>
    <p>저장소 · <a href="https://github.com/dandacompany/paperclip-hermes-codex-on-hostinger">github.com/dandacompany/paperclip-hermes-codex-on-hostinger</a></p>
    <p>SSH/CLI 직접 배포 가이드 · <a href="../tutorial-ssh-cli/tutorial-ssh-cli.html">docs/tutorial-ssh-cli/</a></p>
    <p>Hostinger 콘솔 배포 가이드 · <a href="../tutorial-hostinger-console/tutorial-hostinger-console.html">docs/tutorial-hostinger-console/</a></p>
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
