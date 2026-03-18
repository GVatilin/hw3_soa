#!/usr/bin/env sh
set -e

alembic -c /app/booking_service/alembic.ini upgrade head
exec uvicorn booking_service.app.main:app --host 0.0.0.0 --port "${BOOKING_APP_PORT:-8000}"
