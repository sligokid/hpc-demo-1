# 11-sop/docker — Run Teleprompter Script Generator in Docker

Generates a teleprompter script (`.teleprompter.md`) from a SOP file using a local Ollama model, packaged as a CPU-only Docker container.

---

## Prerequisites

- Docker running locally
- Ollama running on the host with `qwen2.5:7b` pulled

```bash
ollama pull qwen2.5:7b
```

---

## Build

Build context is the project root:

```bash
docker build -f 11-sop/docker/Dockerfile -t slick-plus-teleprompter .
```

The run script builds automatically on first use if the image is not found.

---

## Running

```bash
# From project root
bash 11-sop/docker/run-teleprompter.sh inbox/en/my-procedure.sop.md
```

Reads:

- `sync/input/{lang}/{stem}.sop.md` — mounted read-only at `/sync/input`

Writes:

- `sync/output/{lang}/{stem}.teleprompter.md` — mounted at `/sync/output`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `qwen2.5:7b` | Ollama model name |
| `OLLAMA_HOST` | `ollama:11434` | Ollama service on the `hpc-demo-1_default` Docker network |
| `TELEPROMPTER_IMAGE` | `slick-plus-teleprompter` | Docker image name to run |

```bash
MODEL=llama3.1:8b OLLAMA_HOST=myhost:11434 \
  bash 11-sop/docker/run-teleprompter.sh inbox/en/my-procedure.sop.md
```

---

## How it works

- `run-teleprompter.sh` derives `{lang}` and `{stem}` from the SOP file path, creates `sync/output/{lang}/` if needed, then calls `docker run` with `sync/input/` and `sync/output/` bind-mounted.
- The container joins `hpc-demo-1_default` (the compose project network) so it can reach the `ollama` service by name.
- The image is `python:3.11-slim` — no GPU, no PyTorch. The only dependencies are those in `11-sop/requirements.txt`.

---

## Files

| File | Role |
|---|---|
| `Dockerfile` | Builds the teleprompter image from `python:3.11-slim` |
| `run-teleprompter.sh` | Host-side runner: auto-builds image, mounts volumes, invokes container |
