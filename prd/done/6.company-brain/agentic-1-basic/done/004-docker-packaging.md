## Parent PRD

`issues/prd-v1.md`

## What to build

Package the agent as a Docker image and add it as a service to the existing `docker-compose.yml` at the project root. After this issue, the full stack (Qdrant, Ollama, embed-server, index-server, agent) starts with a single `docker compose up`.

**`10-agent/docker/Dockerfile`**
Follows the pattern of `6-embed/docker/Dockerfile`. Base image: `python:3.11-slim`. Copies `10-agent/` contents into the image. Installs dependencies from `10-agent/docker/requirements.txt`. Sets `ENTRYPOINT ["python", "agent.py"]`. Does not include model weights — the HuggingFace cache is bind-mounted at runtime via `HF_HOME`.

**`10-agent/docker/requirements.txt`**
Pins all dependencies used by `agent.py` and `tools.py`: `langgraph`, `langchain-ollama`, `qdrant-client`, `sentence-transformers`, and any transitive dependencies needed.

**`10-agent/docker/build.sh`**
Builds the image as `slickplus/agent:latest`. Follows the pattern of `6-embed/docker/docker-buildx-publish.sh`.

**`docker-compose.yml` (project root — existing file)**
A new `agent` service is added. It:
- Builds from `10-agent/docker/Dockerfile`
- Depends on `qdrant` and `ollama` (both already defined with health checks)
- Uses internal Docker service hostnames: `QDRANT_HOST=qdrant:6333`, `OLLAMA_HOST=ollama:11434`
- Sets `HF_HOME=/workspace/.hf_cache` (consistent with existing `dev` service)
- Bind-mounts the project root as `/workspace`
- Sets `stdin_open: true` and `tty: true` for interactive terminal use
- No existing service definitions are modified

The agent image can also be run standalone without docker-compose:
```bash
docker run -it \
  --network host \
  -e QDRANT_HOST=localhost:6333 \
  -e OLLAMA_HOST=localhost:11434 \
  -v $(pwd)/.hf_cache:/root/.cache/huggingface \
  slickplus/agent:latest
```

## Acceptance criteria

- [ ] `docker build -f 10-agent/docker/Dockerfile -t slickplus/agent:latest .` succeeds from project root
- [ ] `bash 10-agent/docker/build.sh` builds the image successfully
- [ ] `docker run -it slickplus/agent:latest` (with `--network host` and env vars) starts the agent and presents a `>` prompt
- [ ] `docker compose up agent` starts the agent connected to the Qdrant and Ollama services defined in the existing compose file
- [ ] The image does not contain model weights — `.hf_cache` is bind-mounted
- [ ] No existing services in `docker-compose.yml` are modified or broken
- [ ] `docker compose up` (full stack) starts all services without error

## Blocked by

- Blocked by `issues/003-artefact-generation-governance.md`

## User stories addressed

- User story 1 (`docker run -it slickplus/agent:latest`)
- User story 3 (env var configuration works in container)
- User story 4 (HF cache bind-mounted, not baked in)
- User story 20 (agent service added to existing docker-compose.yml)
