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

COPY pyproject.toml ./

# ------------------------------------------------------------------ dev
FROM base AS dev

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && pip install --no-cache-dir ".[dev]" \
 && apt-get purge -y build-essential libpq-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . .

RUN chmod +x ./entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ----------------------------------------------------------------- prod
FROM base AS prod

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && pip install --no-cache-dir . \
 && apt-get purge -y build-essential libpq-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY . .

# /var/backups/app exists here so the backups volume, created empty on first
# mount, takes its owner from this directory rather than being root's.
RUN chmod +x ./entrypoint.sh \
 && useradd --system --create-home --uid 10001 app \
 && mkdir -p /app/staticfiles /app/media /var/backups/app \
 && chown -R app:app /app /var/backups/app

USER app

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000"]
