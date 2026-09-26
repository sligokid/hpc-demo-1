# 7-index — Index Server

Flask service that receives pre-computed vectors from `6-embed` and writes them to Qdrant. No model dependency — startup is near-instant and the process is lightweight enough to run on a CPU-only node.

**Port:** 8766
**Depends on:** Qdrant (port 6333)

---

## Models Used

None — this service performs no model inference. Vectors are received pre-computed from `6-embed` and written directly to Qdrant.

---

## How it Works

1. **Receive** — `pipeline.py` posts the vector batch returned by `6-embed` to `POST /index`, along with `video_id`, `file`, and `lang`.
2. **Upsert chunks** — each vector is stored as a point in the `video_chunks` Qdrant collection. The point ID is derived deterministically from `video_id` + chunk index using UUID5, so re-running the pipeline on the same file overwrites existing points cleanly.
3. **Upsert metadata** — `pipeline.py` then calls `POST /metadata` with the analysis result from `3-analyze` merged with sentiment from `5-sentiment`. A single record is upserted to `video_metadata` keyed by `video_id`.
4. **Collections** — both collections are created automatically on startup if they do not exist.

**Concurrency:** Flask runs with `threaded=True` so multiple pipeline array tasks can write simultaneously.

---

## Sample Output

`POST /index` response:

```json
{"indexed": 12}
```

`POST /metadata` response:

```json
{"indexed": 1}
```

After indexing, scroll the collections to verify:

```bash
# Chunks
curl -s http://localhost:6333/collections/video_chunks/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit": 3, "with_payload": true, "with_vector": false}'

# Metadata
curl -s http://localhost:6333/collections/video_metadata/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit": 3, "with_payload": true, "with_vector": false}'
```

---

## Files

| File | Description |
|---|---|
| `index_server.py` | Flask server — `POST /index` writes chunks to Qdrant, `POST /metadata` writes video metadata |
| `test_index_server.py` | Unit tests (QdrantClient mocked) |
| `local/1-start-qdrant.sh` | Start a local Qdrant instance via Docker |
| `local/2-start-index-server.sh` | Start the index server locally with the venv |
| `local/3-test-index-curl.sh` | Smoke-test — indexes synthetic vectors, posts metadata, scrolls both collections to verify |
| `local/4-scroll-collection.sh` | Inspect all indexed records in `video_metadata` |
| `hpc/1-qdrant-serve-sbatch.sh` | SLURM service job — runs Qdrant inside Singularity on LUMI |
| `hpc/2-index-serve-sbatch.sh` | SLURM service job — runs the index server on a CPU node on LUMI |
| `docker/Dockerfile` | `linux/amd64` lightweight image (no PyTorch) |
| `docker/requirements.txt` | Python dependencies (`flask`, `qdrant-client`) |

---

## API

### `GET /health`

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

### `POST /metadata`

Write a single metadata record to the `video_metadata` collection.

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

---

## Qdrant Collections

Both collections are created automatically on startup if they do not exist.

| Collection | Vector dim | Distance | Purpose |
|---|---|---|---|
| `video_chunks` | 1024 | Cosine | One point per transcript chunk — searched by `8-search` |
| `video_metadata` | 1 (placeholder) | Cosine | One point per video — scrolled by `9-graph` for the knowledge graph and playlist |

The `video_metadata` collection uses a 1-dim placeholder vector; it is never queried by vector — only scrolled by payload filter.

---

## Running locally

**Prerequisites:** Docker available for Qdrant; venv active for the index server.

```bash
# 1. Start Qdrant
7-index/local/1-start-qdrant.sh

# 2. Start the index server (blocks — run in a separate terminal)
7-index/local/2-start-index-server.sh

# 3. Smoke-test with synthetic vectors (no embed-server needed)
7-index/local/3-test-index-curl.sh

# 4. Inspect what was indexed
7-index/local/4-scroll-collection.sh
```

---

## Docker

The image has no PyTorch dependency — only `flask` and `qdrant-client`, so it builds quickly and stays small.

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

Runs Qdrant inside Singularity on a `small-g` GPU node. Storage is persisted to `$SCRATCH/qdrant-storage`.

**Prerequisites:** SIF pulled:

```bash
singularity pull /scratch/project_465003359/mcgowank/qdrant.sif \
    docker://qdrant/qdrant:latest
```

```bash
sbatch 7-index/hpc/1-qdrant-serve-sbatch.sh
```

Once healthy, writes `$SCRATCH/qdrant.endpoint` containing `<hostname>:6333`.

### 2. Index server (`hpc/2-index-serve-sbatch.sh`)

Runs on a `small` CPU-only node. Reads `$SCRATCH/qdrant.endpoint` to locate Qdrant and fails fast if that file is absent.

```bash
# Submit after Qdrant is ready
sbatch 7-index/hpc/2-index-serve-sbatch.sh

# Or chain with a dependency
JID=$(sbatch --parsable 7-index/hpc/1-qdrant-serve-sbatch.sh)
sbatch --dependency=after:$JID 7-index/hpc/2-index-serve-sbatch.sh
```

Once healthy, writes `$SCRATCH/index.endpoint` containing `<hostname>:8766`.

Logs go to `logs/qdrant-slurm-<jobid>.out` and `logs/index-slurm-<jobid>.out`.

---

## Pipeline integration

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

