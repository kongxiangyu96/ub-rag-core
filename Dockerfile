FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    HF_HOME=/app/.model_cache \
    MODEL_CACHE_DIR=/app/.model_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch \
    && pip install --no-cache-dir .

RUN mkdir -p /app/.model_cache && chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
