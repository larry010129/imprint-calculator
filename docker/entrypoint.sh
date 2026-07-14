#!/bin/sh
set -e

# Render sets PORT dynamically; default for local Docker.
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

if [ -n "${DATABASE_URL}" ] && ! echo "${DATABASE_URL}" | grep -q '^sqlite:'; then
  echo "Running database migrations..."
  # Retry briefly — managed Postgres can lag behind the web service on first boot.
  i=0
  until python -m flask db upgrade; do
    i=$((i + 1))
    if [ "$i" -ge 10 ]; then
      echo "Migrations failed after retries."
      exit 1
    fi
    echo "DB not ready yet (attempt $i/10), waiting..."
    sleep 3
  done
fi

echo "Starting Diamond Calculator on ${HOST}:${PORT}..."
exec python app.py
