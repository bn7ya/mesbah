#!/bin/sh
# Wait for Postgres, migrate, then hand over to the container's command.
#
# Only the web container should migrate; worker and beat wait for the schema
# rather than racing each other to create it.
set -e

python <<'PY'
import os, sys, time
import psycopg

dsn = (
    f"host={os.environ.get('POSTGRES_HOST', 'db')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

for attempt in range(60):
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            sys.exit(0)
    except psycopg.OperationalError:
        time.sleep(1)

print("database did not become available in 60s", file=sys.stderr)
sys.exit(1)
PY

case "$1" in
  celery)
    # Workers do not migrate. Give the web container a moment to finish.
    python manage.py migrate --check >/dev/null 2>&1 || sleep 5
    ;;
  *)
    python manage.py migrate --noinput

    if [ "${DJANGO_DEBUG:-0}" != "1" ]; then
      python manage.py collectstatic --noinput --clear
    fi

    # Idempotent: exits non-zero if the username already exists, which is fine.
    if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
      python manage.py createsuperuser --noinput 2>/dev/null || true
    fi
    ;;
esac

exec "$@"
