# Python 3.12 — required by psycopg 3.3.x (>=3.10) and matches production deps.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app:app \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance static/uploads/products \
    && chmod +x docker/entrypoint.sh

# Render injects $PORT at runtime; EXPOSE is documentation only.
EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
