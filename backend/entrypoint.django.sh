#!/bin/sh
# Wait for Postgres, migrate, seed the one local operator account, then hand
# over to the container's command.
#
# Only the web container should migrate/seed; worker and beat wait for the
# schema rather than racing the web container to create it.
set -e

python <<'PY'
import os, sys, time
import psycopg

dsn = (
    f"host={os.environ.get('POSTGRES_HOST', 'db')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', 'misbah')} "
    f"user={os.environ.get('POSTGRES_USER', 'misbah')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', 'misbah')}"
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
    python manage.py seed_default_operator

    if [ "${DJANGO_DEBUG:-0}" != "1" ]; then
      python manage.py collectstatic --noinput --clear
    fi
    ;;
esac

exec "$@"
