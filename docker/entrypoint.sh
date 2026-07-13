#!/bin/sh
set -e

if [ -n "${DATABASE_URL}" ] && ! echo "${DATABASE_URL}" | grep -q '^sqlite:'; then
  echo "Running database migrations..."
  python -m flask db upgrade
fi

echo "Starting Diamond Calculator on ${HOST}:${PORT}..."
exec python app.py
