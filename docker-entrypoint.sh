#!/bin/sh
set -e

alembic upgrade head

python -c "from app.db import seed; seed()"

exec gunicorn app.main:app \
  --workers "${GUNICORN_WORKERS:-3}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}"
