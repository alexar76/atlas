# ATLAS — physical sensor map (single container: API + SPA).
# Build from monorepo root:
#   docker compose -f atlas/docker-compose.yml up -d --build
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ATLAS_HOST=0.0.0.0 \
    ATLAS_PORT=9330

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY atlas/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY atlas/backend/app /app/app
COPY atlas/frontend/public /app/frontend/public
COPY atlas/config/model_providers.example.yaml /app/config/model_providers.yaml

ENV ATLAS_LLM_CONFIG=/app/config/model_providers.yaml \
    ATLAS_LLM_PROVIDER=deepseek_api \
    ATLAS_LLM_MODEL=deepseek-v4-pro \
    ATLAS_LLM_MODEL_LIGHT=deepseek-v4-flash \
    ATLAS_LLM_BASE_URL=https://api.deepseek.com/v1

EXPOSE 9330

HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${ATLAS_PORT}/health" || exit 1

# Single worker: in-memory aggregator + SSE fan-out must not be sharded.
CMD ["sh", "-c", "uvicorn app.main:app --host ${ATLAS_HOST} --port ${ATLAS_PORT} --workers 1 --limit-concurrency 200 --timeout-keep-alive 30"]
