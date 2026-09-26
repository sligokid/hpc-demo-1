# 6-embed — Embedding Server

Flask service that loads `intfloat/multilingual-e5-large` once and encodes transcript chunks into 1024-dim vectors on demand. Returns raw vectors to the caller — no Qdrant dependency. Writing vectors to the database is handled by the downstream `7-index` service.

**Port:** 8765

---

## Files

| File | Description |
|---|---|
| `embed_server.py` | Flask server — `POST /embed` returns 1024-dim normalised vectors |
| `test_embed_server.py` | Unit tests (SentenceTransformer mocked) |
| `local/1-start-embed-server.sh` | Start the server locally with the venv |
| `local/2-test-embed-curl.sh` | Smoke-test the running server with curl |
| `hpc/1-embed-serve-sbatch.sh` | SLURM service job — runs inside Singularity on LUMI |
| `docker/Dockerfile` | `linux/amd64` CPU image (LUMI-compatible) |
| `docker/requirements.txt` | Python dependencies for the image |
| `docker/docker-buildx-publish.sh` | Build and push the image to Docker Hub |

---

## API

### `GET /health`

Liveness check.

```
200 OK
{"status": "ok"}
```

### `POST /embed`

Encode a batch of transcript chunks. The `passage:` prefix is applied internally — callers send plain text.

**Request:**
```json
{
  "chunks": [
    {"text": "Step one: isolate the circuit.", "timestamp_start": 0.0, "timestamp_end": 3.4},
    {"text": "Step two: verify with a meter.",  "timestamp_start": 3.4, "timestamp_end": 6.1}
  ]
}
```

**Response:**
```json
{
  "vectors": [
    {"text": "Step one: isolate the circuit.", "ts_start": 0.0, "ts_end": 3.4, "vector": [0.012, -0.034, ...]},
    {"text": "Step two: verify with a meter.",  "ts_start": 3.4, "ts_end": 6.1, "vector": [0.008,  0.019, ...]}
  ]
}
```

Each `vector` is a 1024-element float list, L2-normalised. The array order matches the input chunk order.

---

## Model

`intfloat/multilingual-e5-large` — 560M parameter multilingual encoder, supports 100+ languages. Vectors are 1024-dimensional and normalised, so cosine similarity reduces to a dot product.

The `passage:` prefix is prepended to every chunk before encoding. Queries sent from `8-search/search.py` use the `query:` prefix. This asymmetric prompting is required by the E5 model — omitting it degrades retrieval quality.

The model is loaded once at startup and held in memory for the lifetime of the process. Startup takes ~60–90 seconds on a CPU-only instance; subsequent requests are fast.

---

## Running locally

**Prerequisites:** venv active, `pip install -r requirements.txt` done.

```bash
# 1. Start the server (blocks — run in a separate terminal)
6-embed/local/1-start-embed-server.sh

# 2. Smoke-test with curl
6-embed/local/2-test-embed-curl.sh
```

Override the host if the server is running elsewhere:

```bash
EMBED_HOST=http://10.0.0.5:8765 6-embed/local/2-test-embed-curl.sh
```

---

## Docker

The image is `linux/amd64` CPU-only (LUMI-compatible). The build context is the **project root** so the Dockerfile can copy `6-embed/embed_server.py` directly.

```bash
# Build locally
docker build -f 6-embed/docker/Dockerfile -t embed-server .

# Run
docker run -p 8765:8765 embed-server

# Build and push to Docker Hub (amd64)
6-embed/docker/docker-buildx-publish.sh
```

In `docker-compose.yml` the service is named `embed-server`. The `7-index` index-server and the `dev` container both depend on it being healthy before pipeline runs start.

---

## Running on LUMI (HPC)

`hpc/1-embed-serve-sbatch.sh` launches the server as a persistent SLURM job on a GPU node (`small-g` partition). It writes an endpoint file to `$SCRATCH/embed.endpoint` once the health check passes, which downstream jobs read to discover the server address.

**Prerequisites:** SIF pulled to scratch:

```bash
singularity pull /scratch/project_465003359/mcgowank/embeddings-api.sif \
    docker://sligokid/embeddings-api:latest
```

**Submit standalone:**

```bash
sbatch 6-embed/hpc/1-embed-serve-sbatch.sh
```

**Chain with the index service** (index server starts only after embed server is ready):

```bash
JID=$(sbatch --parsable 6-embed/hpc/1-embed-serve-sbatch.sh)
sbatch --dependency=after:$JID 7-index/hpc/2-index-serve-sbatch.sh
```

Logs go to `logs/embed-slurm-<jobid>.out`. The job stays alive until wall time (8 hours) or the server process exits — pipeline jobs can run against it throughout that window.

---

## Pipeline integration

`pipeline.py` calls `POST /embed` to get vectors, then forwards them to `7-index` via `POST /index`. The embed server has no knowledge of Qdrant or video metadata — it only encodes text.

```
… → Sentiment (5-sentiment) → Embed (6-embed) → Index (7-index) → …
```

Configure in `pipeline.yaml`:

```yaml
embed:
  enabled: true
  server_url: http://localhost:8765
```

Override at runtime with the `EMBEDDING_SERVER_URL` environment variable.

---

## Tests

```bash
pytest 6-embed/ -v
```

SentenceTransformer is mocked — no model weights, GPU, or running server required.
