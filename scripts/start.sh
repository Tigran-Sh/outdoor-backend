#!/usr/bin/env sh
set -e

# Collect static assets (Swagger/ReDoc, admin) and apply migrations
# before starting the application server.
python manage.py collectstatic --noinput
python manage.py migrate --noinput

exec gunicorn outdoor_backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
