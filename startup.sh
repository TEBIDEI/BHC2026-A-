#!/bin/sh
set -e
python -m flask --app app db upgrade
if [ "$SEED_ON_START" = "1" ]; then
  python -m flask --app app seed
fi
exec python -m gunicorn "app:create_app()" --bind "0.0.0.0:${PORT:-8000}" --workers 2 --threads 4 --timeout 120 --access-logfile -
