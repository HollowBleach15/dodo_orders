#!/bin/sh
echo "Waiting for migrations..."
python manage.py migrate --noinput
exec celery -A dodo_orders beat -l info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler