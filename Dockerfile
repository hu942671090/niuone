# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim-bookworm

LABEL org.opencontainers.image.title="NiuOne" \
      org.opencontainers.image.description="Local-first market research dashboard and automation workspace" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    NIUONE_CONTAINER_DATA_DIR=/data \
    NIUONE_CONTAINER_HOST=0.0.0.0 \
    NIUONE_CONTAINER_PORT=8787

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 niuone \
    && useradd --uid 10001 --gid 10001 --create-home \
        --home-dir /home/niuone --shell /usr/sbin/nologin niuone

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --disable-pip-version-check --requirement requirements.txt

COPY app/ ./app/
COPY --chmod=755 scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

RUN mkdir -p /data/runtime/cron/state /data/runtime/cron/output /data/runtime/logs \
    && chown -R 10001:10001 /data

USER niuone:niuone

VOLUME ["/data"]
EXPOSE 8787
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; u='http://127.0.0.1:%s/' % os.environ.get('NIUONE_CONTAINER_PORT', '8787'); urllib.request.urlopen(urllib.request.Request(u, method='HEAD'), timeout=3).close()"]

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["dashboard"]
