# syntax=docker/dockerfile:1.7

# ----------------------------------------------------------------- base
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq for psycopg, curl for the healthcheck, gettext for makemessages.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl gettext \
 && rm -rf /var/lib/apt/lists/*

# Dependencies install from pyproject.toml alone, before the code is copied, so a code change
# does not reinstall them. uv reads the list without building the package (ADR-003).
RUN pip install --no-cache-dir "uv>=0.9,<1"

COPY pyproject.toml ./

# ------------------------------------------------------------------ dev
FROM base AS dev

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && uv pip install --system --no-cache -r pyproject.toml --extra dev \
 && apt-get purge -y build-essential libpq-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . .

RUN chmod +x ./entrypoint.sh

ENV MESBAH_DATA_DIR=/data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "config.asgi:application", "--host=0.0.0.0", "--port=8000", "--reload"]

# ------------------------------------------------------------------- ml
# The built-in engine and the trainer: prod plus torch and the training parts. TORCH_INDEX picks
# the build, `cpu` here and CUDA in compose.gpu.yaml.
FROM base AS ml

ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && uv pip install --system --no-cache torch --index-url "${TORCH_INDEX}" \
 && uv pip install --system --no-cache -r pyproject.toml --extra train --extra gguf \
 && apt-get purge -y build-essential libpq-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . .

RUN chmod +x ./entrypoint.sh \
 && useradd --system --create-home --uid 10001 app \
 && mkdir -p /data \
 && chown -R app:app /app /data

USER app

ENV MESBAH_DATA_DIR=/data \
    HF_HOME=/data/hf

EXPOSE 8078
ENTRYPOINT []
CMD ["python", "-m", "mesbah.runtime", "--host=0.0.0.0", "--port=8078"]

# ----------------------------------------------------------------- prod
FROM base AS prod

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && uv pip install --system --no-cache -r pyproject.toml \
 && apt-get purge -y build-essential libpq-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . .

# /var/backups/app exists here so the backups volume, created empty on first
# mount, takes its owner from this directory rather than being root's.
RUN chmod +x ./entrypoint.sh \
 && useradd --system --create-home --uid 10001 app \
 && mkdir -p /app/staticfiles /app/media /var/backups/app /data \
 && chown -R app:app /app /var/backups/app /data

USER app

ENV MESBAH_DATA_DIR=/data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "config.asgi:application", "--host=0.0.0.0", "--port=8000", "--proxy-headers", "--forwarded-allow-ips=*"]
