# Embedding server — linux/amd64 CPU-only image (LUMI-compatible).
# Encodes text and returns vectors; no Qdrant dependency.
# Build context: project root (docker compose sets context: .)

FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY 6-embed/docker/requirements.txt requirements.txt

RUN pip install --no-cache-dir \
        torch \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY 6-embed/embed_server.py .

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD curl -sf http://localhost:8765/health || exit 1

CMD ["python", "embed_server.py", "--port", "8765"]
