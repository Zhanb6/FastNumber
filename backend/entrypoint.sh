#!/bin/sh
set -eu

echo "[entrypoint] applying migrations"
alembic upgrade head

echo "[entrypoint] startup step (settings, singletons, admin, optional seed)"
python -m app.startup

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
