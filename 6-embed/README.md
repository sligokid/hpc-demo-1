# 6-embed — Embedding Server

Flask service that loads `intfloat/multilingual-e5-large` once and encodes transcript chunks into 1024-dim vectors on demand. Returns raw vectors to the caller — no Qdrant dependency. Writing vectors to the database is handled by the downstream `7-index` service.

**Port:** 8765

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `intfloat/multilingual-e5-large` | [HuggingFace](https://huggingface.co/intfloat/multilingual-e5-large) | Encodes transcript chunks into 1024-dim vectors; supports 100+ languages |

560M parameter multilingual encoder. Vectors are 1024-dimensional and L2-normalised, so cosine similarity reduces to a dot product. Downloaded automatically on first run and cached in `$HF_HOME`.

---

## How it Works

1. **Startup** — the server loads `intfloat/multilingual-e5-large` into memory once. Startup takes ~60–90s on CPU; subsequent requests are fast.
2. **Request** — `pipeline.py` sends all transcript chunks for one audio file as a single `POST /embed` payload.
3. **Prefix** — each chunk text is prefixed with `passage:` as required by the E5 model before encoding.
4. **Encode** — `SentenceTransformer.encode()` runs the batch through the model and returns L2-normalised 1024-dim vectors.
5. **Response** — vectors are returned as JSON to `pipeline.py`, which forwards them immediately to `7-index` for storage in Qdrant. The embed server never touches Qdrant.

The `passage:` prefix is used for indexing; queries from `8-search/search.py` use `query:`. This asymmetric prompting is required by E5 — omitting it degrades retrieval quality.

**Concurrency:** Flask runs with `threaded=True` so multiple pipeline array tasks can send requests simultaneously.

---

## Sample Output

`POST /embed` response:

```json
{
  "vectors": [
    {
      "text": "and now i'd like to show you how to create a slick",
      "ts_start": 0.0,
      "ts_end": 4.2,
      "vector": [0.0124, -0.0341, 0.0089, "...1021 more floats..."]
    },
    {
      "text": "we've made this process as simple as possible",
      "ts_start": 4.2,
      "ts_end": 8.7,
      "vector": [0.0098, 0.0192, -0.0057, "...1021 more floats..."]
    }
  ]
}
```

Each vector is 1024 floats, L2-normalised (magnitude = 1.0). Array order matches input chunk order.

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

The image is `linux/amd64` CPU-only (LUMI-compatible). The build context is the **project root**.

```bash
# Build locally
docker build -f 6-embed/docker/Dockerfile -t embed-server .

# Run
docker run -p 8765:8765 embed-server

# Build and push to Docker Hub (amd64)
6-embed/docker/docker-buildx-publish.sh
```

In `docker-compose.yml` the service is named `embed-server`.

---

## Running on LUMI (HPC)

`hpc/1-embed-serve-sbatch.sh` launches the server as a persistent SLURM job on a GPU node (`small-g` partition). It writes an endpoint file to `$SCRATCH/embed.endpoint` once the health check passes.

**Prerequisites:** SIF pulled to scratch:

```bash
singularity pull /scratch/project_465003359/mcgowank/embeddings-api.sif \
    docker://sligokid/embeddings-api:latest
```

```bash
# Submit standalone
sbatch 6-embed/hpc/1-embed-serve-sbatch.sh

# Chain with index service
JID=$(sbatch --parsable 6-embed/hpc/1-embed-serve-sbatch.sh)
sbatch --dependency=after:$JID 7-index/hpc/2-index-serve-sbatch.sh
```

Logs go to `logs/embed-slurm-<jobid>.out`.

---

## Pipeline integration

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
