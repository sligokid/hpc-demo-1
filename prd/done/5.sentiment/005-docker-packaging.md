## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

Package every new Task 2 component into the existing Docker Compose setup so the full pipeline runs with a single `docker compose up`. No component in this issue should be built from scratch — this is purely packaging and integration of what passed Phase 1 (local) verification.

Deliverables:
- **`5-embed/docker/Dockerfile`** — amd64-compatible image for `embed-server.py`
- **`docker-compose.yml`** — add `qdrant` and `embed-server` services to the existing file
- **`5-embed/docker/1-run-pipeline.sh`** — end-to-end Docker pipeline demo script
- **`5-embed/test_embed.py`** — unit tests for embed-server, sentiment, and label covering: chunk ingestion, Qdrant write, sentiment scoring, JSONL label output

See PRD: Phase 2 — Docker section and Deliverables #17–19.

## Acceptance criteria

- [ ] `docker compose up -d` starts Qdrant + Ollama + embed-server with no manual steps
- [ ] `docker compose run --rm dev python pipeline.py --file <sample>` processes a file end-to-end
- [ ] `docker compose run --rm dev python search.py --query "..."` returns results
- [ ] `docker compose run --rm dev python graph.py` produces `graph.json`
- [ ] `docker compose run --rm dev python playlist.py --user user@org.com` returns a playlist
- [ ] `pytest 5-embed/test_embed.py` passes with all tests green
- [ ] `5-embed/docker/Dockerfile` builds for `linux/amd64` (required for LUMI compatibility)

## Blocked by

- Blocked by `issues/002-embed-server-and-search-local.md`
- Blocked by `issues/003-sentiment-and-auto-labelling.md`
- Blocked by `issues/004-knowledge-graph-and-playlist.md`

## User stories addressed

- The full pipeline must be reproducible by any team member with `docker compose up` — no local Python environment required.
- Docker packaging is the mandatory gate before HPC deployment per the PRD's three-environment rule.
