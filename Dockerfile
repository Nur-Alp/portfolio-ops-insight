FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 osip \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin osip

COPY requirements.lock pyproject.toml ./
COPY backend ./backend
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./

RUN python -m pip install --require-hashes -r requirements.lock \
    && python -m pip install --no-deps . \
    && mkdir -p /var/lib/osip/source-files \
    && chown -R osip:osip /var/lib/osip

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]

CMD ["uvicorn", "osip_dashboard.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
