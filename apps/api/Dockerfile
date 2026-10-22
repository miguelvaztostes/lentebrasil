FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api/src:/app/workers/ingestion

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends --yes libarchive-tools \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
RUN pip install --no-cache-dir '/app/apps/api[dev]'

COPY apps/api /app/apps/api
COPY workers/ingestion /app/workers/ingestion
COPY docs/catalog/input/lente_inventario_nacional_fontes_2026.json /app/docs/catalog/input/lente_inventario_nacional_fontes_2026.json

WORKDIR /app/apps/api
CMD ["sh", "-c", "alembic upgrade head && python -m lente_api.catalog import /app/docs/catalog/input/lente_inventario_nacional_fontes_2026.json && uvicorn lente_api.main:app --host 0.0.0.0 --port 8000"]

