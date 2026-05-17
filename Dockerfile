# syntax=docker/dockerfile:1.7

FROM ghcr.io/hostinger/hvps-hermes-agent:latest AS hermes
# hermes 설치 위치: /opt/hermes (venv: /opt/hermes/.venv/bin/hermes)
# ttyd 위치: /usr/bin/ttyd

FROM ghcr.io/hostinger/hvps-paperclip:latest

USER root

# tini for proper PID 1 signal handling + zombie reaping (not present in base image)
# python3 (3.13) is required by /opt/hermes/.venv/bin/python which symlinks to /usr/bin/python3
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini python3 \
 && rm -rf /var/lib/apt/lists/*

# Hermes 전체 설치본 복사 (venv 포함 — Python 바이너리는 경로 절대 의존)
# NOTE: Full Python venv required — minimum 750MB without optimization. Tracked for v1.1 slim-down.
# Use --chown to set ownership at copy time (recursive chown on millions of venv files would OOM).
COPY --from=hermes --chown=node:node /opt/hermes /opt/hermes
# ttyd 바이너리 복사
COPY --from=hermes /usr/bin/ttyd /usr/local/bin/ttyd

# hermes CLI를 PATH에 노출
ENV PATH=/opt/hermes/.venv/bin:$PATH

# Custom entrypoint + supervisor + codex auth + hermes ttyd wrapper
COPY scripts/entrypoint.sh   /entrypoint.sh
COPY scripts/supervisor.sh   /usr/local/bin/supervisor.sh
COPY scripts/codex-oauth.sh  /usr/local/bin/codex-oauth.sh
COPY scripts/hermes-tty.sh   /usr/local/bin/hermes-tty.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/supervisor.sh /usr/local/bin/codex-oauth.sh /usr/local/bin/hermes-tty.sh

# 영구 데이터 디렉터리 (named volume mount target)
RUN mkdir -p /paperclip /home/node/.hermes /home/node/.codex \
 && chown -R node:node /home/node/.hermes /home/node/.codex /paperclip


# Patch hermes-paperclip-adapter to use Hermes's own configured default
# when agent's adapterConfig.model is empty, instead of falling back to
# anthropic/claude-sonnet-4. Mirrors upstream PR #123 (OPEN):
#   https://github.com/NousResearch/hermes-paperclip-adapter/pull/123
# Once upstream merges and a new base image picks it up, this sed
# becomes a no-op (idempotent).
RUN ADAPTER_JS=/usr/local/lib/node_modules/paperclipai/node_modules/hermes-paperclip-adapter/dist/server/execute.js \
 && sed -i 's#cfgString(config\.model) || DEFAULT_MODEL#cfgString(config.model)#g' "$ADAPTER_JS" \
 && REMAIN=$(grep -c 'cfgString(config.model) || DEFAULT_MODEL' "$ADAPTER_JS" 2>/dev/null || echo 0) \
 && echo "remaining DEFAULT_MODEL fallbacks: $REMAIN"

ENV HOME=/home/node
ENV HERMES_HOME=/home/node/.hermes
USER node
EXPOSE 3100 9119 4860
ENTRYPOINT ["tini","-g","--","/entrypoint.sh"]
