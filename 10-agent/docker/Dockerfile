# Agent — linux/amd64 CPU-only image (LUMI-compatible).
# Runs the LangGraph RAG agent; connects to Qdrant and Ollama as external services.
# Build context: project root (docker compose sets context: .)
# Model weights are NOT baked in — bind-mount HF_HOME at runtime.

FROM --platform=linux/amd64 python:3.11-slim

# /app holds agent source; /workspace is available for bind-mounts (e.g. HF cache)
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY 10-agent/docker/requirements.txt requirements.txt

RUN pip install --no-cache-dir \
        torch \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY 10-agent/agent.py .
COPY 10-agent/tools.py .
COPY 10-agent/prompts.py .

ENTRYPOINT ["python", "/app/agent.py"]
