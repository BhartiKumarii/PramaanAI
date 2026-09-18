#!/bin/sh
# Runs on every container start (both local docker-compose and Render):
# apply any pending migrations, then idempotently seed the two demo
# accounts, then start the API. All three steps are safe to repeat.
set -e

alembic upgrade head
python -m scripts.seed_demo_users
python -m scripts.seed_citizen_registry
python -m scripts.seed_blacklist_registry

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
