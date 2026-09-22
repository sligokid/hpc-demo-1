# 5-embed — Sentiment, Embedding, Indexing & Semantic Search

This folder covers **Stages 4 and 5** of the SLICK+ pipeline — sentiment scoring and vector indexing. Together they transform transcript segments and Ollama-extracted metadata into a searchable, sentiment-aware knowledge base.

### Stage 4 — Sentiment (`sentiment.py`)

After `analyze.py` produces `analysis.json`, `pipeline.py` passes the transcript segments to `sentiment.py`. It scores the full transcript using `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilingual, no GPU required) and returns a `sentiment_label` (positive / neutral / negative) and a `sentiment_score`. These two fields are merged directly into the metadata dict before it is sent to Qdrant — so every `video_metadata` record carries sentiment as a first-class payload field.

```
analyze.py → analysis.json
                  │
                  ▼
            sentiment.py  ← runs on segments (or splits transcript if segments unavailable)
                  │
                  ▼
            metadata + sentiment_label + sentiment_score  → POST /metadata → Qdrant
```

### Stage 5 — Embed & Index (`embed-server.py`)

`embed-server.py` loads `intfloat/multilingual-e5-large` once at startup and exposes two HTTP endpoints called by `pipeline.py`:

- `POST /embed` — receives the Whisper segment list, encodes each chunk into a 1024-dim vector, upserts into `video_chunks`
- `POST /metadata` — receives the merged metadata dict (including sentiment fields from Stage 4), stores it in `video_metadata`

Both collections are then queryable by `search.py` and consumed by `6-graph/` to build the knowledge graph and personalised playlists.

**What this enables:**
- A factory worker searches "how do I clear a jam on line 3" and gets back the exact timestamp in an internal video where a colleague demonstrates the fix — in their own language.
- A floor manager filters `video_metadata` by `sentiment_label` to spot topics that skew negative across the Arabic-language library.
- `6-graph/graph.py` colours graph nodes by sentiment; `6-graph/playlist.py` can filter or boost by sentiment label.

**Components:**
- `sentiment.py` — Stage 4: per-video sentiment scoring, output merged into metadata before indexing
- `embed-server.py` — Stage 5: HTTP service that embeds chunks and upserts both collections into Qdrant
- `label.py` — calls Llama 3 to produce JSONL sentiment training data for future fine-tuning (training deferred to Phase 2)
- `search.py` (project root) — CLI tool that queries `video_chunks` and returns timestamped results

Blocks on: `2-inference/infer.py --segments` (issue 001) — each chunk carries `timestamp_start`/`timestamp_end` from `segments.json`.

### What sentiment adds

**Content routing in playlists.** Sentiment becomes a filter, not just metadata. Onboarding playlists can prefer positive-sentiment videos — upbeat, confident delivery — while risk and compliance training can deliberately surface negative-sentiment content where experienced workers describe what went wrong. Without sentiment, `playlist.py` has no way to make that distinction; it only knows tags.

**Organisational health signal in the graph.** A manager looking at the knowledge graph who sees a cluster of negative-sentiment nodes all tagged `equipment` and `arabic` has a signal they could not get from a flat file system: something about how Arabic-speaking workers talk about equipment is consistently negative. That might mean a knowledge gap, a training failure, a team under stress, or a real safety hazard. No individual employee is flagged — it is an aggregate pattern surfaced without any additional tooling.

**Metadata enrichment that compounds downstream.** Because sentiment is merged into the `video_metadata` payload before indexing, every future tool that reads Qdrant gets it for free — the graph, the playlist, any future search filter, a future insights dashboard. It costs one model pass per video at pipeline time and then it is just a field. If it were added later it would require re-processing every video already in the collection.

**Current limitation.** The model (`twitter-xlm-roberta`) was trained on social media text, not factory floor speech. It will misclassify confident technical language as neutral and understated safety warnings as positive. The `label.py` silver-labelling pipeline exists to generate domain-specific training data to fix this in Phase 2 — but until that fine-tuned model ships, sentiment labels should be treated as directional signals rather than ground truth.

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

## Running on HPC (LUMI)

### Step 1 — build and push the amd64 Docker image

Run once from a machine with Docker Buildx (e.g. your laptop or a CI runner):

```bash
docker buildx build --platform linux/amd64 -t sligokid/embeddings-api:latest --push -f 5-embed/docker/Dockerfile .
```

### Step 2 — pull SIFs on LUMI

Run once from a LUMI login node with internet access:

```bash
singularity pull /scratch/project_465003209/mcgowank/qdrant.sif docker://qdrant/qdrant:latest
singularity pull /scratch/project_465003209/mcgowank/embeddings-api.sif docker://sligokid/embeddings-api:latest
```

### Step 3 — start the services

Submit from the project root. Qdrant must be running before the embed server starts so its endpoint file is present:

```bash
JID=$(sbatch --parsable 5-embed/hpc/qdrant-serve-sbatch.sh)
sbatch --dependency=after:$JID 5-embed/hpc/embeddings-serve-sbatch.sh
```

Or let `restart-services-sbatch.sh` manage the full service lifecycle (it waits 2 minutes for Qdrant before submitting the embed server):

```bash
sbatch restart-services-sbatch.sh
```

Monitor with `squeue -u $USER`. Logs at `logs/qdrant-slurm-<jobid>.out` and `logs/embed-slurm-<jobid>.out`.

The Qdrant service writes `$SCRATCH/qdrant.endpoint` (`hostname:6333`) when ready; the embed server reads it to connect. The embed server writes `$SCRATCH/embed.endpoint` (`hostname:8765`) when warm.

## Files

| File | Role |
|------|------|
| `embed-server.py` | Flask HTTP service — embeds and indexes transcript chunks |
| `local/1-start-qdrant.sh` | Start Qdrant via Docker |
| `local/2-start-embed-server.sh` | Start embed-server.py |
| `local/3-run-pipeline.sh` | End-to-end pipeline run on a sample file |
| `hpc/qdrant-serve-sbatch.sh` | SLURM service job — runs Qdrant SIF on a GPU node (D-qdrant) |
| `hpc/embeddings-serve-sbatch.sh` | SLURM service job — runs embed-server inside the embeddings-api SIF (E-embed) |
| `test_embed_server.py` | Unit tests for embed-server (mocked, no GPU or Qdrant needed) |
| `../search.py` | CLI search tool — query Qdrant and return timestamped results |
| `../test_search.py` | Unit tests for search.py |
