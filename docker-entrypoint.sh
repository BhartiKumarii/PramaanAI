#!/bin/sh
# Runs on every container start (both local docker-compose and Render):
# apply any pending migrations, then idempotently seed demo data,
# then start the API. All steps are safe to repeat.
set -e

alembic upgrade head
python -m scripts.seed_demo_users
python -m scripts.seed_citizen_registry
python -m scripts.seed_blacklist_registry
python -m scripts.seed_demo_cases

# PRAMAAN_WORKERS = uvicorn worker processes (not WEB_CONCURRENCY, which a
# host may preset for its own sizing) (each loads its own models;
# ~1-1.5 GB RAM per worker with OCR + face + YOLO). The API keeps no
# per-request state in memory, so more workers or more instances behind a
# load balancer scale it horizontally.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${PRAMAAN_WORKERS:-1}"
