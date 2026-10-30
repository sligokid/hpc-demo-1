## Parent PRD

`issues/prd.md`

## What to build

Docker deployment for `12-tts`: a `Dockerfile`, a `run-tts.sh` convenience script, and a `docker-buildx-publish.sh` build/push script.

- `12-tts/docker/Dockerfile` — `python:3.11-slim`, linux/amd64, installs `requirements.txt`, copies `tts.py`, entrypoint `python /app/tts.py`
- `12-tts/docker/run-tts.sh` — runs the image with `sync/input` mounted read-only and `sync/output` read-write; auto-builds the image if not present; respects `OLLAMA_HOST`, `VOICE`, and `TTS_IMAGE` env vars
- `12-tts/docker/docker-buildx-publish.sh` — builds and pushes `sligokid/tts-tools:latest` for linux/amd64 from the project root build context

Follows the exact pattern of `11-sop/docker/`.

## Acceptance criteria

- [ ] `12-tts/docker/Dockerfile` builds successfully with `docker build`
- [ ] Container entrypoint is `python /app/tts.py`
- [ ] `run-tts.sh` accepts a teleprompter file path, mounts volumes correctly, and passes flags to the container
- [ ] `run-tts.sh` auto-builds the image if `TTS_IMAGE` is not found locally
- [ ] `OLLAMA_HOST` defaults to `ollama:11434` (Docker network default) inside the container run
- [ ] `docker-buildx-publish.sh` targets `linux/amd64` and pushes `sligokid/tts-tools:latest`
- [ ] Build context is project root (not `12-tts/`) so `COPY` paths resolve correctly

## Blocked by

- `issues/tts/075-tts-core.md`

## User stories addressed

- User story 9
- User story 10
