## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

A thin vertical slice that takes a transcribed audio file all the way from `segments.json` → chunked embeddings → Qdrant → searchable timestamped results, running entirely on a developer laptop.

Three new components:

1. **`5-embed/embed-server.py`** — HTTP service that loads `intfloat/multilingual-e5-large` once, accepts POST batches of text chunks, and writes 1024-dim vectors to a local Qdrant instance. Creates `video_chunks` and `video_metadata` collections on startup.
2. **`search.py`** — CLI tool: `python search.py --query "..." --lang es --top-k 5` returns JSON with `file`, `timestamp_start`, `score`, `text`.
3. **Local startup scripts** — `5-embed/local/1-start-qdrant.sh`, `5-embed/local/2-start-embed-server.sh`, `5-embed/local/3-run-pipeline.sh`.

Also integrates Stage 5 (embed + index) into `pipeline.py` so the full pipeline runs end-to-end on a single file.

See PRD: Architecture, Qdrant Schema, Embedding Model, CLI Tools sections and Deliverables #3, #7, #14–16.

## Acceptance criteria

- [ ] `bash 5-embed/local/1-start-qdrant.sh` starts Qdrant on port 6333 with no manual steps
- [ ] `python 5-embed/embed-server.py --qdrant-host localhost:6333` starts without error and logs readiness
- [ ] `pipeline.py` processes a single sample file through all 5 stages (transcribe → extract → sentiment stub → embed → index)
- [ ] `python search.py --query "..." --top-k 5` returns at least one result with `timestamp_start` populated
- [ ] `video_chunks` collection exists in Qdrant with correct 1024-dim schema after a pipeline run
- [ ] `video_metadata` collection exists in Qdrant with correct payload fields after a pipeline run
- [ ] `5-embed/local/3-run-pipeline.sh` runs end-to-end with no manual steps

## Blocked by

- Blocked by `issues/001-whisper-segments-output.md` (chunks must carry `timestamp_start`/`timestamp_end` from `segments.json`)

## User stories addressed

- A new hire searches "how do I clear a jam on line 3" and gets a ranked list of videos with exact timestamps.
- The system must make all video knowledge semantically searchable with timestamped retrieval across 5 languages (PRD Goal 1).
