# 7-index — Index Server

Flask service that receives pre-computed vectors from `6-embed` and writes them to Qdrant. No model dependency — startup is near-instant and the process is lightweight enough to run on a CPU-only node.

**Port:** 8766
**Depends on:** Qdrant (port 6333)

---

## Files

| File | Description |
|---|---|
| `index_server.py` | Flask server — `POST /index` writes chunks to Qdrant, `POST /metadata` writes video metadata |
| `test_index_server.py` | Unit tests (QdrantClient mocked) |
| `local/1-start-qdrant.sh` | Start a local Qdrant instance via Docker |
| `local/2-start-index-server.sh` | Start the index server locally with the venv |
| `local/3-test-index-curl.sh` | Smoke-test the running server — indexes synthetic vectors, posts metadata, then scrolls both Qdrant collections to verify |
| `local/4-scroll-collection.sh` | Inspect all indexed records — shows `sentiment_label`, `sentiment_score`, and `video_id` for every entry in `video_metadata` |
| `hpc/1-qdrant-serve-sbatch.sh` | SLURM service job — runs Qdrant inside Singularity on LUMI |
| `hpc/2-index-serve-sbatch.sh` | SLURM service job — runs the index server on a CPU node on LUMI |
| `docker/Dockerfile` | `linux/amd64` lightweight image (no PyTorch) |
| `docker/requirements.txt` | Python dependencies (`flask`, `qdrant-client`) |

---

## API

### `GET /health`

Liveness check.

```
200 OK
{"status": "ok"}
```

### `POST /index`

Write a batch of pre-computed vectors to the `video_chunks` collection.

**Request:**
```json
{
  "video_id": "en/safety-intro",
  "file": "inbox/en/safety-intro.mp3",
  "lang": "en",
  "vectors": [
    {"text": "Step one: isolate the circuit.", "ts_start": 0.0, "ts_end": 3.4, "vector": [0.012, -0.034, ...]},
    {"text": "Step two: verify with a meter.",  "ts_start": 3.4, "ts_end": 6.1, "vector": [0.008,  0.019, ...]}
  ]
}
```

**Response:**
```json
{"indexed": 2}
```

Point IDs are derived deterministically from `video_id` and chunk index using UUID5, so re-running the pipeline on the same file overwrites existing points rather than creating duplicates.

### `POST /metadata`

Write a single metadata record to the `video_metadata` collection. Accepts any JSON dict — all fields are stored as payload. Typical fields come from `3-analyze` (`title`, `description`, `tags`, `uploaded_by`) plus `5-sentiment` (`sentiment_label`, `sentiment_score`).

**Request:**
```json
{
  "video_id": "en/safety-intro",
  "file": "inbox/en/safety-intro.mp3",
  "lang": "en",
  "title": "Electrical Safety Introduction",
  "tags": ["safety", "electrical", "onboarding"],
  "sentiment_label": "positive",
  "sentiment_score": 0.41
}
```

**Response:**
```json
{"indexed": 1}
```

The point ID is derived from `video_id` using UUID5, so reruns overwrite cleanly.

---

## Qdrant collections

Both collections are created automatically on startup if they do not exist.

| Collection | Vector dim | Distance | Purpose |
|---|---|---|---|
| `video_chunks` | 1024 | Cosine | One point per transcript chunk — searched by `8-search` |
| `video_metadata` | 1 (placeholder) | Cosine | One point per video — read by `9-graph` for the knowledge graph and playlist |

The `video_metadata` collection uses a 1-dim placeholder vector; it is never queried by vector — only scrolled by payload filter.

---

## Running locally

**Prerequisites:** Docker available for Qdrant; venv active for the index server.

```bash
# 1. Start Qdrant
7-index/local/1-start-qdrant.sh
# → http://localhost:6333  (dashboard: http://localhost:6333/dashboard)

# 2. Start the index server (blocks — run in a separate terminal)
7-index/local/2-start-index-server.sh

# 3. Smoke-test with synthetic vectors (no embed-server needed)
7-index/local/3-test-index-curl.sh

# 4. After running the pipeline, inspect what was indexed
7-index/local/4-scroll-collection.sh
```

Override the Qdrant host if it is running elsewhere:

```bash
QDRANT_HOST=http://10.0.0.5:6333 7-index/local/3-scroll-collection.sh
```

---

## Docker

The image has no PyTorch dependency — it installs only `flask` and `qdrant-client`, so it builds in seconds and stays small.

```bash
# Build locally
docker build -f 7-index/docker/Dockerfile -t index-server .

# Run (Qdrant must be reachable at qdrant:6333 inside the network)
docker run -p 8766:8766 index-server
```

In `docker-compose.yml` the service is named `index-server` and depends on `qdrant` being healthy. The `dev` container is passed `INDEX_SERVER_URL=http://index-server:8766` so `pipeline.py` finds it automatically.

---

## Running on LUMI (HPC)

Two SLURM jobs are required: Qdrant and the index server. Both write endpoint files to `$SCRATCH` so downstream jobs can discover them.

### 1. Qdrant (`hpc/1-qdrant-serve-sbatch.sh`)

Runs Qdrant inside Singularity on a `small-g` GPU node. Storage is persisted to `$SCRATCH/qdrant-storage` across job restarts.

**Prerequisites:** SIF pulled:

```bash
singularity pull /scratch/project_465003359/mcgowank/qdrant.sif \
    docker://qdrant/qdrant:latest
```

**Submit:**

```bash
sbatch 7-index/hpc/1-qdrant-serve-sbatch.sh
```

Once healthy, writes `$SCRATCH/qdrant.endpoint` containing `<hostname>:6333`.

### 2. Index server (`hpc/2-index-serve-sbatch.sh`)

Runs on a `small` CPU-only node — no GPU or Singularity needed. Reads `$SCRATCH/qdrant.endpoint` to locate Qdrant and fails fast if that file is absent.

**Submit after Qdrant is ready:**

```bash
sbatch 7-index/hpc/2-index-serve-sbatch.sh
```

**Or chain both with a dependency:**

```bash
JID=$(sbatch --parsable 7-index/hpc/1-qdrant-serve-sbatch.sh)
sbatch --dependency=after:$JID 7-index/hpc/2-index-serve-sbatch.sh
```

Once healthy, writes `$SCRATCH/index.endpoint` containing `<hostname>:8766`.

Both jobs stay alive until wall time (8 hours). Logs go to `logs/qdrant-slurm-<jobid>.out` and `logs/index-slurm-<jobid>.out`.

---

## Pipeline integration

`pipeline.py` calls `POST /index` with the vectors returned by `6-embed`, then calls `POST /metadata` with the analysis result from `3-analyze` merged with the sentiment result from `5-sentiment`.

```
… → Embed (6-embed) → Index (7-index) → …
                              ↓
                          Qdrant
                        (video_chunks,
                        video_metadata)
                              ↓
                   Search (8-search) / Graph (9-graph)
```

Configure in `pipeline.yaml`:

```yaml
index:
  server_url: http://localhost:8766
```

Override at runtime with the `INDEX_SERVER_URL` environment variable.

---

## Tests

```bash
pytest 7-index/ -v
```

QdrantClient is mocked throughout — no running Qdrant instance required.
