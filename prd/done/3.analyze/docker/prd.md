# PRD: Local Docker Compose Setup for Ollama-backed Metadata Generation

## Problem Statement

A developer on a MacBook wants to run `analyze.py` locally against a real Ollama LLM without installing Ollama natively. The existing `docker-compose.yml` provides a `dev` container for running project scripts, but has no Ollama service. There is no established pattern for wiring the `dev` container to an Ollama backend, persisting downloaded model weights across restarts, or pulling models before first use — so the metadata generation step of the pipeline cannot be exercised locally without manual setup outside the project.

## Solution

An `ollama` service is added to the existing `docker-compose.yml`. It runs the official `ollama/ollama` image, exposes port 11434 inside the Docker network, and stores model weights in a named volume so they survive container restarts. A one-time `docker compose run` command pulls the default model into that volume. `analyze.py` gains an `--ollama-host` flag (consistent with the HPC PRD) so the caller can pass `ollama:11434` when running inside the `dev` container. The `dev` container requires no changes beyond what the `--ollama-host` flag provides.

## Pipeline Position

```
audio file
    │
    ▼
docker compose run dev python infer.py  ──►  transcript (text)
                                                   │
                                                   ▼
docker compose run dev python analyze.py \
    --transcript transcript.txt \
    --ollama-host ollama:11434            ──►  metadata (JSON)
                                                   ▲
                                          ollama service (docker compose up ollama)
```

## User Stories

1. As a developer, I want to add an Ollama service to the existing `docker-compose.yml`, so that I do not need to install Ollama natively on my MacBook.
2. As a developer, I want the Ollama service to use the official `ollama/ollama` image, so that I get an up-to-date, supported Ollama binary without building a custom image.
3. As a developer, I want Ollama model weights stored in a named Docker volume, so that models I pull are not lost when I stop or recreate the container.
4. As a developer, I want a single documented command to pull the default model (`llama3`) into the named volume before first use, so that I can get started without reading Ollama documentation.
5. As a developer, I want `analyze.py` to accept an `--ollama-host` flag (default `localhost:11434`), so that I can point it at the Docker-networked Ollama service by passing `ollama:11434`.
6. As a developer, I want the default value of `--ollama-host` to remain `localhost:11434`, so that existing local usage of `analyze.py` outside Docker is not broken.
7. As a developer, I want the `ollama` service to be reachable from the `dev` container at `ollama:11434` via Docker's internal DNS, so that no port mapping or IP address configuration is required.
8. As a developer, I want to start the Ollama service with `docker compose up ollama`, so that it runs in the background while I run scripts in the `dev` container.
9. As a developer, I want to run `analyze.py` inside the existing `dev` container via `docker compose run dev python analyze.py --ollama-host ollama:11434`, so that I use the same Python environment and workspace mount as all other project scripts.
10. As a developer, I want clear documentation of the three-step local setup (start service, pull model, run script), so that I can onboard without tribal knowledge.
11. As a developer, I want the named volume for Ollama models to be declared in the top-level `volumes` block of `docker-compose.yml`, so that it is managed by Docker Compose and visible in `docker volume ls`.
12. As a developer, I want a `healthcheck` on the `ollama` service that polls `/api/tags`, so that `docker compose ps` shows a meaningful ready state and I know when the service is available.
13. As a developer, I want the Ollama service to restart automatically if it crashes (via `restart: unless-stopped`), so that it stays available across long local working sessions without manual intervention.
14. As a developer, I want `analyze.py` to produce a clear error message if it cannot reach the host specified by `--ollama-host`, so that I can diagnose a stopped Ollama container immediately.
15. As a developer, I want the error message to include the value of `--ollama-host` that was used, so that I can confirm I passed the right address.
16. As a developer, I want to be able to swap the model by passing `--model mistral` to `analyze.py`, so that I can test other models I have pulled into the named volume without code changes.
17. As a developer, I want the Ollama service to expose port 11434 on the host as well as inside the Docker network, so that I can also call it from scripts running directly in my shell (outside the `dev` container) using `localhost:11434`.

## Implementation Decisions

### Modules

- **`docker-compose.yml`** (modified) — add an `ollama` service using the `ollama/ollama` image. Mount the named volume at `/root/.ollama` inside the container (Ollama's default model storage path). Expose port `11434:11434`. Add a `healthcheck` polling `http://localhost:11434/api/tags`. Set `restart: unless-stopped`. Declare the named volume in the top-level `volumes` block.

- **`analyze.py`** (modified) — add `--ollama-host` CLI flag with default `localhost:11434`. Replace the hardcoded base URL with one constructed from this flag: `http://<ollama_host>/api/generate`. Error messages on connection failure include the value of `--ollama-host`.

### Key architectural decisions

- **Named volume, not bind mount** — model weights are large (llama3 8B is ~5 GB) and are not source files. A named volume keeps them out of the project directory, out of `.dockerignore` concerns, and managed by Docker's own lifecycle.

- **Explicit `--ollama-host` flag, not env var** — consistent with the HPC pattern defined in the metadata PRD. The caller decides where Ollama is; the script does not infer it from the environment. This keeps `analyze.py` behaviour predictable regardless of how it is invoked.

- **CPU-only inference** — Docker Desktop on macOS runs inside a Linux VM and cannot access Apple Metal (MPS). Ollama in Docker will use CPU inference only. For latency-sensitive use, running Ollama natively (via `ollama serve`) and pointing `analyze.py` at `localhost:11434` is the faster alternative, but is out of scope for this PRD.

- **No changes to `dev` service or `Dockerfile.dev`** — the `dev` container already has the Python environment and workspace mount needed to run `analyze.py`. Adding Ollama as a sibling service and passing `--ollama-host` is sufficient.

- **One-time model pull** — `docker compose run --rm ollama ollama pull llama3` pulls weights into the named volume. This command is idempotent; re-running it after the model is cached is safe and fast.

### One-time setup commands

```bash
# 1. Start the Ollama service
docker compose up -d ollama

# 2. Pull the default model into the named volume (once)
docker compose exec ollama ollama pull llama3

# 3. Run analyze.py inside the dev container
docker compose run --rm dev python analyze.py \
    --transcript transcripts/my-video.txt \
    --ollama-host ollama:11434
```

## Testing Decisions

**What makes a good test:** test externally observable behaviour of `analyze.py`. Given a known transcript and a mocked HTTP response, assert the correct JSON is returned and the correct URL was called. Do not test Docker networking or Ollama internals.

**Modules to test:**

- **`analyze.py` — `--ollama-host` constructs the correct URL:** mock `requests.post` at the HTTP boundary; assert the call is made to `http://ollama:11434/api/generate` when `--ollama-host ollama:11434` is passed. Consistent with the existing test approach specified in the metadata PRD.

- **`analyze.py` — connection failure includes host in error message:** mock `requests.post` to raise `ConnectionError`; assert exit code 1 and that the error output contains the value passed to `--ollama-host`.

- **`analyze.py` — default host is `localhost:11434`:** assert that when `--ollama-host` is omitted, the URL constructed is `http://localhost:11434/api/generate`.

**Prior art:** same `requests.post` mock boundary used by the metadata PRD tests. No new test infrastructure needed.

## Out of Scope

- GPU acceleration inside Docker on macOS — Docker Desktop cannot access Apple Metal.
- Building a custom Ollama Docker image — the official `ollama/ollama` image is used as-is.
- Baking model weights into a Docker image — weights live in a named volume, pulled at runtime.
- A `docker-compose.override.yml` for CI — CI does not require Ollama or metadata generation.
- Batch processing of multiple transcripts via Docker Compose — single-file invocation only; batching is handled at the shell level.
- Automatic model pulling on service startup — the pull is a documented one-time manual step.
- Networking Ollama across multiple machines on a LAN.
- Any changes to `Dockerfile.dev` or the `dev` service configuration.

## Further Notes

- `ollama/ollama` is the correct image for CPU-only Mac/Linux use. The `ollama/ollama:rocm` variant is for AMD GPU and is not needed here.
- The named volume persists until explicitly removed with `docker volume rm`. Developers should be aware that re-pulling a model is required if the volume is deleted.
- If a developer prefers native Ollama (for Metal GPU acceleration on Apple Silicon), `analyze.py --ollama-host localhost:11434` works unchanged against a native `ollama serve` process — no Docker involvement required.
- The `--ollama-host` flag added here is identical in name and default to the one specified in the HPC PRD (`prd/5.analyze/prd.md`). Both PRDs drive the same code change in `analyze.py`, so the change only needs to be implemented once.
