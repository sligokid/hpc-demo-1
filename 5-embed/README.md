# Embed & Search — Semantic video retrieval

`embed-server.py` loads `intfloat/multilingual-e5-large` once and indexes transcript chunks into a local Qdrant instance. `search.py` (project root) queries those chunks and returns timestamped results.

Blocks on: `2-inference/infer.py --segments` (issue 001) — each chunk carries `timestamp_start`/`timestamp_end` from `segments.json`.

## How it works

```
Audio file
    │
    ▼
infer.py (Whisper)
    │  produces transcript.txt
    │  produces segments.json  ← [{start, end, text}, ...]
    ▼
analyze.py (Ollama / llama3)
    │  produces analysis.json  ← {title, description, tags, goals, skills}
    ▼
pipeline.py  ──POST /embed──►  embed-server.py
    │                               │
    └──POST /metadata──────────────►│  loads multilingual-e5-large (once at startup)
                                    │
                                    ▼
                               Qdrant (local)
                               ┌─────────────────────────────────────────┐
                               │ video_chunks  (1024-dim cosine vectors)  │
                               │   each row = one Whisper segment         │
                               │   payload: file, lang, start, end, text  │
                               ├─────────────────────────────────────────┤
                               │ video_metadata  (per-file metadata)      │
                               │   payload: title, tags, goals, skills…   │
                               └─────────────────────────────────────────┘
                                    ▲
                                    │ query_points(query_vector, limit, filter)
                               search.py
                                    │
                                    ▼
                               [{file, timestamp_start, score, text}, ...]
```

### Indexing path (pipeline.py → embed-server.py → Qdrant)

1. `pipeline.py` calls `transcribe_with_segments()` instead of `transcribe()` when `embed.enabled: true`. This runs Whisper with `return_timestamps=True` and returns the raw segment list alongside the transcript text.
2. Each segment `{start, end, text}` is sent as a chunk to `POST /embed`. The embed server prepends `"passage: "` to each text (required by the E5 model for passages being indexed) and encodes the batch in one call to `SentenceTransformer.encode()`.
3. The 1024-dim vectors are upserted into the `video_chunks` Qdrant collection with the full segment payload attached. Each point gets a random UUID so re-running a pipeline adds new points rather than overwriting — wipe the collection between full re-indexes if needed.
4. After the analyze stage, `pipeline.py` calls `POST /metadata` to store the structured Ollama output (title, description, tags, goals, skills) alongside the file reference in `video_metadata`.

### Search path (search.py → Qdrant)

1. `search.py` loads the same `multilingual-e5-large` model and encodes the user query with the `"query: "` prefix (E5 uses asymmetric prefixes — `"passage: "` at index time, `"query: "` at search time).
2. `query_points()` performs approximate nearest-neighbour search against `video_chunks` using cosine similarity. An optional `Filter` on the `lang` payload field narrows results to one language.
3. Results are returned as `[{file, timestamp_start, score, text}]` — enough for a UI to deep-link directly to the moment in the video.

## Running locally

### Step 1 — start Qdrant

```bash
bash 5-embed/local/1-start-qdrant.sh
```

Starts `qdrant/qdrant` on port 6333 via Docker with a named volume so data persists across restarts. Dashboard at `http://localhost:6333/dashboard`.

### Step 2 — start the embed server

```bash
source venv/bin/activate
bash 5-embed/local/2-start-embed-server.sh
```

Downloads `multilingual-e5-large` on first run (~560 MB). Logs `Ready. Listening on :8765` when warm. Creates `video_chunks` and `video_metadata` collections in Qdrant if they don't exist.

### Step 3 — run the pipeline end-to-end

```bash
bash 5-embed/local/3-run-pipeline.sh
# or a specific file:
bash 5-embed/local/3-run-pipeline.sh 2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3 en
```

Runs `pipeline.py` with `embed.enabled: true` (default in `pipeline.yaml`). Each audio file goes through:

```
transcribe (Whisper) → segments.json → analyze (Ollama) → embed (multilingual-e5-large) → Qdrant
```

### Step 4 — search

```bash
python search.py --query "how do I clear a jam on line 3"
python search.py --query "triathlon" --lang en --top-k 5
```

Returns JSON:

```json
[
  {
    "file": "inbox/en/foo.mp3",
    "timestamp_start": 42.5,
    "score": 0.9134,
    "text": " clear the jam by lifting the guard and pulling the belt..."
  }
]
```

## Flags

### embed-server.py

| Flag | Default | Description |
|------|---------|-------------|
| `--qdrant-host` | `localhost:6333` | Qdrant host:port |
| `--port` | `8765` | Port to listen on |

### search.py

| Flag | Default | Description |
|------|---------|-------------|
| `--query` | required | Natural-language search query |
| `--lang` | none | Filter results by language code (e.g. `es`) |
| `--top-k` | `5` | Number of results to return |
| `--qdrant-host` | `localhost:6333` | Qdrant host:port |

## API

### `POST /embed`

Index a batch of transcript chunks. Called automatically by `pipeline.py`.

```json
{
  "video_id": "en/my-video",
  "file": "inbox/en/my-video.mp3",
  "lang": "en",
  "chunks": [
    { "text": "hello world", "timestamp_start": 0.0, "timestamp_end": 2.5 }
  ]
}
```

Response: `{"indexed": 1}`

### `POST /metadata`

Store per-file analysis metadata (title, description, tags, …) in `video_metadata`. Called automatically by `pipeline.py` after the analyze stage.

### `GET /health`

Returns `{"status": "ok"}` — use this to confirm the server is warm before sending a pipeline run.

## Qdrant schema

| Collection | Dimensions | Distance | Payload fields |
|-----------|-----------|----------|----------------|
| `video_chunks` | 1024 | Cosine | `video_id`, `file`, `lang`, `timestamp_start`, `timestamp_end`, `text` |
| `video_metadata` | 1 (dummy) | Cosine | `video_id`, `file`, `lang`, plus all fields from `analyze.py` output |

## Tests

```bash
pytest 5-embed/test_embed_server.py
pytest test_search.py
```

No model weights or running services required — all external deps are mocked.

## Files

| File | Role |
|------|------|
| `embed-server.py` | Flask HTTP service — embeds and indexes transcript chunks |
| `local/1-start-qdrant.sh` | Start Qdrant via Docker |
| `local/2-start-embed-server.sh` | Start embed-server.py |
| `local/3-run-pipeline.sh` | End-to-end pipeline run on a sample file |
| `test_embed_server.py` | Unit tests for embed-server (mocked, no GPU or Qdrant needed) |
| `../search.py` | CLI search tool — query Qdrant and return timestamped results |
| `../test_search.py` | Unit tests for search.py |
