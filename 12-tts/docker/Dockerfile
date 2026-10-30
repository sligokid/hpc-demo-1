# TTS — linux/amd64 CPU-only image.
# Converts teleprompter markdown to WAV audio via Ollama lfm3-audio.
# Build context: project root  (docker buildx build -f 12-tts/docker/Dockerfile .)

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY 12-tts/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY 12-tts/tts.py .

ENTRYPOINT ["python", "/app/tts.py"]
