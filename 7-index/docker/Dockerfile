# Index server — receives pre-computed vectors, writes to Qdrant.
# No model dependency — lightweight image.
# Build context: project root (docker compose sets context: .)

FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY 7-index/docker/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY 7-index/index_server.py .

EXPOSE 8766

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -sf http://localhost:8766/health || exit 1

CMD ["python", "index_server.py", "--qdrant-host", "qdrant:6333", "--port", "8766"]
