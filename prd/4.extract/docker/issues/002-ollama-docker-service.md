## Parent PRD

`prd/4.extract/docker/prd.md`

## What to build

Add an `ollama` service to `docker-compose.yml` using the official `ollama/ollama` image. The service stores model weights in a named Docker volume, exposes port 11434 on both the host and the internal Docker network, restarts automatically if it crashes, and exposes a healthcheck so `docker compose ps` shows a meaningful ready state.

See PRD §Implementation Decisions > `docker-compose.yml` and §One-time setup commands.

## Acceptance criteria

- [ ] `docker-compose.yml` has an `ollama` service using `ollama/ollama` image
- [ ] Named volume `ollama_models` mounted at `/root/.ollama` inside the container
- [ ] `ollama_models` declared in top-level `volumes` block
- [ ] Port `11434:11434` exposed (host and Docker network)
- [ ] `restart: unless-stopped` set on the `ollama` service
- [ ] Healthcheck polls `http://localhost:11434/api/tags`
- [ ] `docker compose up -d ollama` starts the service successfully
- [ ] `docker compose exec ollama ollama pull llama3` populates the named volume
- [ ] `docker compose run --rm dev python analyze.py --transcript <file> --ollama-host ollama:11434` reaches the ollama service

## Blocked by

None - can start immediately.

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 7
- User story 8
- User story 11
- User story 12
- User story 13
- User story 17
