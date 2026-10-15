#!/usr/bin/env bash
set -euo pipefail
python manage.py prepare_database
python manage.py migrate --noinput
python manage.py ensure_owner
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
