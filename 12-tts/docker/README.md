# 12-tts/docker — Run TTS Generation in Docker

Converts a teleprompter script (`.teleprompter.md`) to a WAV audio file using Ollama `lfm3-audio`, packaged as a CPU-only Docker container.

---

## Prerequisites

- Docker running locally
- Ollama 0.40.11 or later with `lfm3-audio` pulled
- The `hpc-demo-1_default` Docker network (created by `docker compose up`)

```bash
# Verify Ollama version
ollama --version   # must be 0.40.11+

# Pull the TTS model into the Docker Ollama service (one-time, 2.1 GB)
docker compose up -d ollama
docker compose exec ollama ollama pull lfm3-audio
```

> **Note:** `lfm3-audio` runs on linux/amd64 and linux/arm64. `phonon` is Apple Silicon only and cannot be used inside Docker.

---

## Build

Build context is the project root:

```bash
docker build -f 12-tts/docker/Dockerfile -t slick-plus-tts .
```

The run script builds automatically on first use if the image is not found.

---

## Running

```bash
# From project root
bash 12-tts/docker/run-tts.sh results/en/myvideo.teleprompter.md
```

Reads:

- `results/{lang}/{stem}.teleprompter.md` — mounted read-write at `/results`

Writes:

- `results/{lang}/{stem}.teleprompter.wav` — single concatenated WAV (16-bit, mono, 24 kHz)

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `lfm3-audio` | Ollama TTS model name |
| `VOICE` | `male` | Voice name passed to the model |
| `OLLAMA_HOST` | `ollama:11434` | Ollama service on the `hpc-demo-1_default` Docker network |
| `TTS_IMAGE` | `slick-plus-tts` | Docker image name to run |

```bash
MODEL=lfm3-audio VOICE=female bash 12-tts/docker/run-tts.sh results/en/myvideo.teleprompter.md
```

---

## Publishing

The TTS image is included in the project-wide publish script at the project root:

```bash
bash update-docker-repos.sh
```

To push only the TTS image, uncomment the `tts-tools` line in `update-docker-repos.sh` and run it. Pushes `sligokid/tts-tools:latest` for linux/amd64.

---

## How it works

- `run-tts.sh` checks whether `$MODEL` is present in the Docker Ollama service and pulls it if not, then derives `{lang}` and `{stem}` from the teleprompter file path, creates `results/{lang}/` if needed, and calls `docker run` with `results/` bind-mounted.
- The container joins `hpc-demo-1_default` so it can reach the `ollama` service by name.
- The image is `python:3.11-slim` — no GPU, no PyTorch. The only dependency is `requests`.

---

## Files

| File | Role |
|---|---|
| `Dockerfile` | Builds the TTS image from `python:3.11-slim` |
| `run-tts.sh` | Host-side runner: pulls model, auto-builds image, mounts volumes, invokes container |
| `update-docker-repos.sh` (project root) | Builds and pushes all images including `sligokid/tts-tools:latest` |
