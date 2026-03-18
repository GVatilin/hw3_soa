#!/usr/bin/env sh
set -e

alembic -c /app/flight_service/alembic.ini upgrade head
exec uvicorn flight_service.app.main:app --host 0.0.0.0 --port "${FLIGHT_APP_PORT:-8001}"
