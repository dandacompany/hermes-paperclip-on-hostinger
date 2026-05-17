# syntax=docker/dockerfile:1.7

FROM ghcr.io/hostinger/hvps-hermes-agent:latest AS hermes
# hermes 설치 위치: /opt/hermes (venv: /opt/hermes/.venv/bin/hermes)
# ttyd 위치: /usr/bin/ttyd

FROM ghcr.io/hostinger/hvps-paperclip:latest

USER root

# Hermes 전체 설치본 복사 (venv 포함 — Python 바이너리는 경로 절대 의존)
COPY --from=hermes /opt/hermes /opt/hermes
# ttyd 바이너리 복사
COPY --from=hermes /usr/bin/ttyd /usr/local/bin/ttyd

# hermes CLI를 PATH에 노출
ENV PATH=/opt/hermes/.venv/bin:$PATH

# Custom entrypoint + supervisor + codex auth
COPY scripts/entrypoint.sh   /entrypoint.sh
COPY scripts/supervisor.sh   /usr/local/bin/supervisor.sh
COPY scripts/codex-oauth.sh  /usr/local/bin/codex-oauth.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/supervisor.sh /usr/local/bin/codex-oauth.sh

# 영구 데이터 디렉터리 (named volume mount target)
RUN mkdir -p /paperclip /home/node/.hermes /home/node/.codex \
 && chown -R node:node /home/node/.hermes /home/node/.codex /paperclip

USER node
EXPOSE 3100 9119 4860
ENTRYPOINT ["tini","-g","--","/entrypoint.sh"]
