#!/usr/bin/env bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn -c gunicorn.conf.py hospital.asgi:application -k uvicorn.workers.UvicornWorker
