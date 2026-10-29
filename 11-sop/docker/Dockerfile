# Teleprompter — linux/amd64 CPU-only image.
# Generates teleprompter scripts from SOP files via a local Ollama model.
# Build context: project root  (docker compose / docker build -f 11-sop/docker/Dockerfile .)

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY 11-sop/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY 11-sop/ollama_utils.py .
COPY 11-sop/teleprompter.py .

ENTRYPOINT ["python", "/app/teleprompter.py"]
