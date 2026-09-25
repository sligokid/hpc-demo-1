# 5-embed — Sentiment, Embedding, Indexing & Semantic Search

Stages 4 and 5 of the SLICK+ pipeline — sentiment scoring and vector indexing. Transforms transcript segments and Ollama-extracted metadata into a searchable, sentiment-aware knowledge base.

---

## Models

| Model | Purpose | GPU required |
|-------|---------|-------------|
| `cardiffnlp/twitter-xlm-roberta-base-sentiment` | Sentiment scoring — multilingual RoBERTa fine-tuned on Twitter data across 8 languages | No |
| `intfloat/multilingual-e5-large` | Text embedding — 1024-dim vectors covering 100+ languages, ~560 MB | Yes (production) |

`multilingual-e5-large` uses asymmetric prefixes: chunks indexed with `"passage: "`, queries encoded with `"query: "`. This is required by the E5 model and improves retrieval accuracy over symmetric approaches.

> **Sentiment limitation:** `twitter-xlm-roberta` was trained on social media text, not workplace speech. Confident technical language may score as neutral; understated safety warnings may score as positive. `label.py` generates domain-specific training data to address this in Phase 2 — until then, treat sentiment labels as directional signals rather than ground truth.

---

## Stage 4 — Sentiment (`sentiment.py`)

After `analyze.py` produces `analysis.json`, `pipeline.py` passes the transcript to `sentiment.py`, which returns a `sentiment_label` (positive / neutral / negative) and `sentiment_score`. Both fields are merged into the metadata dict before indexing — every `video_metadata` record carries sentiment as a first-class payload field.

```
analyze.py → analysis.json
                  │
                  ▼
            sentiment.py  ← runs on segments (or splits transcript if segments unavailable)
                  │
                  ▼
            metadata + sentiment_label + sentiment_score  → POST /metadata → Qdrant
```

---

## Stage 5 — Embed & Index (`embed-server.py`)

`embed-server.py` loads `multilingual-e5-large` once at startup and exposes two HTTP endpoints called by `pipeline.py`:

- `POST /embed` — receives the Whisper segment list, encodes each chunk into a 1024-dim vector, upserts into `video_chunks`
- `POST /metadata` — receives the merged metadata dict (including sentiment from Stage 4), stores it in `video_metadata`

Both collections are queryable by `search.py` and consumed by `6-graph/` for the knowledge graph and personalised playlists.

---

## What sentiment enables

**Content routing in playlists.** Sentiment becomes a filter, not just metadata. Onboarding playlists can prefer positive-sentiment videos while risk training can deliberately surface negative-sentiment content where workers describe what went wrong.

**Organisational health signal in the graph.** A cluster of negative-sentiment nodes all tagged `equipment` and `arabic` surfaces a pattern — a knowledge gap, training failure, or team stress signal — without flagging any individual employee.

**Metadata enrichment that compounds downstream.** Because sentiment is merged before indexing, every future tool that reads Qdrant gets it for free. Adding it later would require re-processing every video already in the collection.

---

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
                               Qdrant
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

1. `pipeline.py` calls `transcribe_with_segments()` when `embed.enabled: true`, running Whisper with `return_timestamps=True` to produce a segment list alongside the transcript text.
2. Each segment `{start, end, text}` is sent to `POST /embed`. The server prepends `"passage: "` and encodes the batch in one `SentenceTransformer.encode()` call.
3. The 1024-dim vectors are upserted into `video_chunks` with full segment payload. Each point gets a random UUID — re-running the pipeline appends rather than overwrites, so wipe the collection between full re-indexes if needed.
4. After the analyze stage, `pipeline.py` calls `POST /metadata` to store the structured Ollama output in `video_metadata`.

### Search path (search.py → Qdrant)

1. `search.py` encodes the user query with the `"query: "` prefix.
2. `query_points()` performs approximate nearest-neighbour search against `video_chunks` using cosine similarity. An optional `Filter` on `lang` narrows results to one language.
3. Results are returned as `[{file, timestamp_start, score, text}]` — enough to deep-link directly to the moment in the video.

---

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

### Step 3 — smoke-test the embed server (optional)

```bash
bash 5-embed/local/3-test-embeddings-curl.sh
```

Posts a small batch of synthetic chunks, verifies they are stored in Qdrant, then runs a nearest-neighbour search. Useful for confirming the server is warm before processing real audio.

### Step 4 — run the pipeline end-to-end

```bash
bash 5-embed/local/4-run-pipeline.sh
# or a specific file:
bash 5-embed/local/4-run-pipeline.sh 2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3 en
```

Runs `pipeline.py` with `embed.enabled: true` (default in `pipeline.yaml`). Each audio file goes through:

```
transcribe (Whisper) → segments.json → analyze (Ollama) → embed (multilingual-e5-large) → Qdrant
```

### Step 5 — search

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

### Step 6 — inspect the sentiment collection (optional)

```bash
bash 5-embed/local/6-scroll-sentiment-collection.sh
```

Scrolls the `video_metadata` collection and prints `sentiment_label` + `sentiment_score` for all indexed files.

## Running on Docker

### Step 1 — start all services

```bash
docker compose up -d qdrant embed-server ollama
```

Starts Qdrant (port 6333), the embed-server (port 8765), and Ollama in the background. The embed-server container depends on Qdrant, so Docker Compose starts them in the right order. On first run, `multilingual-e5-large` (~560 MB) is downloaded into the container image layer.

### Step 2 — confirm the embed server is ready

```bash
until docker compose exec embed-server curl -sf http://localhost:8765/health > /dev/null 2>&1; do
    echo "not ready yet — retrying in 5s..."
    sleep 5
done
echo "embed-server ready."
```

Or run the full Docker demo script which waits for readiness automatically:

```bash
bash 5-embed/docker/1-run-pipeline.sh
# or a specific file and language:
bash 5-embed/docker/1-run-pipeline.sh inbox/en/foo.mp3 en
```

The script starts services, waits for the embed-server health check, pulls the `llama3` model, processes the audio file through all five pipeline stages, then runs semantic search, knowledge graph export, and playlist generation as a smoke test.

### Step 3 — run individual pipeline tools inside Docker

```bash
docker compose run --rm dev python pipeline.py --file inbox/en/foo.mp3 --lang en
docker compose run --rm dev python search.py --query "how do I clear a jam" --qdrant-host qdrant:6333
docker compose run --rm dev python 6-graph/graph.py --qdrant-host qdrant:6333 --output sync/output/graph.json
docker compose run --rm dev python 6-graph/playlist.py --user engineer@org.com --qdrant-host qdrant:6333
```

Inside Docker Compose the Qdrant hostname is `qdrant` (the service name), not `localhost`.

### Step 4 — run tests

```bash
docker compose run --rm dev pytest 5-embed/test_embed_server.py
```

No GPU, running Qdrant, or model weights required — all external dependencies are mocked.

---

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
singularity pull /scratch/project_465003359/mcgowank/qdrant.sif docker://qdrant/qdrant:latest
singularity pull /scratch/project_465003359/mcgowank/embeddings-api.sif docker://sligokid/embeddings-api:latest
```

### Step 3 — start the services

Submit from the project root. Qdrant must be running before the embed server starts so its endpoint file is present:

```bash
JID=$(sbatch --parsable 5-embed/hpc/1-qdrant-serve-sbatch.sh)
sbatch --dependency=after:$JID 5-embed/hpc/2-embeddings-serve-sbatch.sh
```

Monitor with `squeue -u $USER`. Logs at `logs/qdrant-slurm-<jobid>.out` and `logs/embed-slurm-<jobid>.out`.

The Qdrant service writes `$SCRATCH/qdrant.endpoint` (`hostname:6333`) when ready; the embed server reads it to connect. The embed server writes `$SCRATCH/embed.endpoint` (`hostname:8765`) when warm.

## EU AI Act Compliance

> **Human review gate:** The compliance language in this section must be reviewed and approved by a human before this README is merged. CSC's Senior Coordinator for Trustworthy AI has assessed SLICK+ as not high-risk under the EU AI Act based on its role as a knowledge-sharing and learning tool — not a system for recruitment, employee evaluation, performance monitoring, or discipline. The constraints below follow from that assessment and are **design requirements, not optional configuration**.

### Constraints

1. **No individual performance scoring.** The personalisation engine must not generate per-employee engagement scores visible to managers.

2. **Opt-out required.** Employees must be able to disable personalisation and browse all content freely without any record being kept of that choice.

3. **No management-visible engagement data in standard mode.** Watch history used for playlist ranking is used only to personalise the individual's own experience.

4. **Consent-based data collection.** Any use of real employee video or audio data requires a signed Data Processing Agreement before processing on LUMI-G infrastructure (required before Task 3 enterprise pilot).

5. **Training data for this PRD uses public FLEURS data and synthetic/dummy inputs only.** No real employee data is processed until the Task 3 DPA is in place.

### How `--no-personalise` satisfies the opt-out requirement

When an employee runs:

```bash
python 6-graph/playlist.py --user engineer@org.com --no-personalise
```

`playlist.py` skips all personalisation logic entirely:

- Watch history is **not read** from the user profile.
- Role tags are **not loaded** from `roles.yaml`.
- No scoring is applied — results are returned in alphabetical order by filename.
- The `--no-personalise` flag is transient: it is a CLI argument, not written back to the profile or logged anywhere. **No record of the opt-out choice is kept.**

The same behaviour is triggered by setting `"personalise": false` in the user's `profiles/<user>.json`. This satisfies constraint 2 above: the employee gets full unfiltered access to the content library and the system retains no signal that personalisation was disabled.

Constraint 1 is satisfied structurally: `playlist.py` outputs a ranked list of videos for the requesting user only. There is no manager-facing endpoint, no aggregate engagement dashboard, and no per-employee score field in the `video_metadata` Qdrant collection. The `_score` field in playlist output is visible only in the CLI response to the requesting user's own session.

## Files

| File | Role |
|------|------|
| `embed_server.py` | Flask HTTP service — embeds and indexes transcript chunks |
| `sentiment.py` | Stage 4: per-video sentiment scoring via xlm-roberta |
| `label.py` | Llama 3 auto-labelling of transcript chunks for fine-tuning data |
| `local/1-start-qdrant.sh` | Start Qdrant via Docker |
| `local/2-start-embed-server.sh` | Start embed_server.py natively |
| `local/3-test-embeddings-curl.sh` | Smoke-test embed-server and Qdrant via curl |
| `local/4-run-pipeline.sh` | End-to-end pipeline run on a sample file |
| `local/5-search-vector-db.sh` | Run semantic search against Qdrant |
| `local/6-scroll-sentiment-collection.sh` | Inspect sentiment fields across all indexed videos |
| `docker/Dockerfile` | embed-server image (amd64 compatible for LUMI) |
| `docker/1-run-pipeline.sh` | End-to-end Docker demo: starts services, processes file, runs search/graph/playlist |
| `hpc/1-qdrant-serve-sbatch.sh` | SLURM service job — runs Qdrant SIF on a GPU node (D-qdrant) |
| `hpc/2-embeddings-serve-sbatch.sh` | SLURM service job — runs embed-server inside the embeddings-api SIF (E-embed) |
| `test_embed_server.py` | Unit tests for embed-server (mocked, no GPU or Qdrant needed) |
| `../search.py` | CLI search tool — query Qdrant and return timestamped results |
| `../test_search.py` | Unit tests for search.py |
| `../6-graph/playlist.py` | CLI personalised playlist generator (opt-out aware via `--no-personalise`) |
