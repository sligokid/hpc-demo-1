# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning & Knowledge Extraction Pipeline

**Goal: Turning speech & video into machine-readable knowledge at HPC scale.**

---

## Pipeline Overview

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 1: TRAINING                               │
  │  Fine-tune openai/whisper-small on Google FLEURS                         │
  │  en · es · fr · zh-CN · ar  (5 parallel SLURM GPU jobs)                  │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  checkpoints/<lang>/
                                 ▼
─────────────────────────────────────────────────────────────────────────────

  ┌──────────────────┐
  │   Google Drive   │◄── [ Upload mp3 / mp4 / wav / flac / m4a / ogg ]
  │ whisper-sync/    │
  │   input/         │
  └────────┬─────────┘
           │  rclone (C-sync · every 5 min)
           ▼
  ┌──────────────────┐
  │  LUMI HPC        │
  │   sync/input/    │
  └────────┬─────────┘
           │  Z-poll (every 10 min) → pipeline-hpc-submit.sh → SLURM array
           ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        STAGE 2: TRANSCRIBE                               │
  │  infer.py — Whisper (AMD/ROCm GPU, fine-tuned checkpoint)                │
  │  Chunked 30s windows · any-length audio · 5-second overlap               │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  sync/output/<lang>/<stem>.transcript.txt
                                 │                         .segments.json
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                         STAGE 3: ANALYSE                                 │
  │  analyze.py — Llama 3 via Ollama (B-ollama GPU daemon)                   │
  │  Extracts: title · description · tags · goals · skills                   │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  sync/output/<lang>/<stem>.analysis.json
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        STAGE 5: SENTIMENT                                │
  │  sentiment.py — cardiffnlp/twitter-roberta-base-sentiment-latest         │
  │  Majority-vote label + signed mean score across transcript chunks         │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  { sentiment_label, sentiment_score }
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 6: EMBED                                  │
  │  embed_server.py — intfloat/multilingual-e5-large (D-embed · port 8765)  │
  │  Encodes transcript chunks → 1024-dim L2-normalised vectors              │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  { vectors: [{text, ts_start, ts_end, vector}] }
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 7: INDEX                                  │
  │  index_server.py — Flask (F-index · port 8766)                           │
  │  Writes chunk vectors → Qdrant video_chunks                              │
  │  Writes video metadata → Qdrant video_metadata  (E-qdrant · port 6333)  │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │
                    ┌────────────┴─────────────┐
                    ▼                           ▼
  ┌────────────────────────┐   ┌───────────────────────────────────────────┐
  │      STAGE 8: SEARCH   │   │               STAGE 9: GRAPH              │
  │  search.py             │   │  graph.py — knowledge graph (nodes/edges) │
  │  Semantic nearest-     │   │  playlist.py — ranked personalised        │
  │  neighbour lookup over │   │  playlist from video_metadata             │
  │  video_chunks          │   │  (G-graph)                                │
  └────────────────────────┘   └───────────────────────────────────────────┘
                                 │
           rclone (C-sync · every 5 min)
                                 ▼
  ┌──────────────────┐
  │   Google Drive   │◄── sync/output/ (transcripts · analysis · graph.html)
  │ whisper-sync/    │
  │   output/        │
  └──────────────────┘
```

> **Note:** Stage 4 (file sync) is the background rclone loop — not an inline processing stage. It feeds `sync/input/` and drains `sync/output/` independently on a 5-minute cycle.

---

## Local Development

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Full Pipeline Locally

Start required services (each in its own terminal):

```bash
ollama serve && ollama pull llama3.1:8b   # Llama 3 for 3-analyze
docker run -p 6333:6333 qdrant/qdrant     # Qdrant for 7-index / 8-search / 9-graph
6-embed/local/1-start-embed-server.sh     # embedding server (port 8765)
7-index/local/2-start-index-server.sh     # index server (port 8766)
```

Then run the pipeline:

```bash
./pipeline-local.sh

# Or run directly with options
python pipeline.py --lang en
python pipeline.py --file sync/input/en/sample.mp3
```

### Run via Docker Compose

```bash
docker compose up
```

All services (Ollama, Qdrant, embed-server, index-server, dev) are defined in `docker-compose.yml`.

---

## Testing

```bash
# Unit tests — all stages
pytest 2-inference/test_infer.py
pytest 3-analyze/test_analyze.py
pytest 5-sentiment/
pytest 6-embed/
pytest 7-index/
pytest 8-search/
pytest 9-graph/

# Or run all at once
pytest 2-inference/ 3-analyze/ 5-sentiment/ 6-embed/ 7-index/ 8-search/ 9-graph/

# Smoke tests
bash 4-file-sync/test-sync.sh
bash 7-index/local/3-test-index-curl.sh

# Shell script tests (BATS)
make test
```

No GPU, model weights, or running services required for unit tests — all external dependencies are mocked.

---

### Launch the Pipeline Locally (Docker)

**Prerequisites:** Docker Desktop running, `rclone` installed and configured (see [`4-file-sync/README.md`](4-file-sync/README.md)).

```bash
# Start (or restart) all persistent services — ollama, qdrant, embed-server, index-server
./restart-services-docker.sh

# Rebuild images first if you've changed code
./restart-services-docker.sh --build
```

Services and ports once healthy:

| Service | Port | Dashboard |
|---|---|---|
| `ollama` | 11434 | — |
| `qdrant` | 6333 | http://localhost:6333/dashboard |
| `embed-server` | 8765 | http://localhost:8765/health |
| `index-server` | 8766 | http://localhost:8766/health |

Then run the pipeline:

```bash
./pipeline-docker.sh
```

---

### Launch the Pipeline on LUMI

**Prerequisites:** Singularity SIFs in scratch (`whisper-hpc.sif`, `whisper-sync.sif`, `ollama.sif`, `embeddings-api.sif`, `qdrant.sif`), rclone config at `~/.config/rclone/rclone.conf`, and Llama weights pulled (see `3-analyze/hpc/3-ollama-pull-llama3.sh`).

```bash
cd /scratch/project_465003359/mcgowank/hpc-demo-1

# Start (or restart) all services — cancels any running instances, resubmits all, resubmits itself every 12 h
sbatch restart-services-sbatch.sh                    # A-restart
```

`restart-services-sbatch.sh` submits B-ollama → C-sync → D-embed → E-qdrant → F-index → Z-poll in the correct dependency order, then reschedules itself every 12 hours to keep services fresh.

Wait for B-ollama, D-embed, E-qdrant, and F-index to reach `R` (running) and write their endpoint files to `$SCRATCH` before processing begins.

```
             JOBID PARTITION     NAME     USER ST       TIME  NODES
          22100084   small-g B-ollama mcgowank  R      12:31      1
          22100150     small   C-sync mcgowank  R       8:17      1
          22100201   small-g   D-embed mcgowank  R       6:04      1
          22100210     small E-qdrant mcgowank  R       5:58      1
          22100212     small  F-index mcgowank  R       5:51      1
          22100106     small   Z-poll mcgowank PD       0:00      1
```

### Manual Batch Submission

```bash
# Process all pending files
./pipeline-hpc-submit.sh

# Restrict to one language
./pipeline-hpc-submit.sh --lang en

# Chain with a dependency
JID=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
./pipeline-hpc-submit.sh --dependency after:$JID
```

### Graph and Playlist (on demand)

After files are indexed, run the graph job to produce `sync/output/graph.json`, `graph.html`, and playlist JSON:

```bash
sbatch 9-graph/hpc/graph-sbatch.sh
sbatch 9-graph/hpc/graph-sbatch.sh --user engineer@org.com --top-n 10
```

## Automated HPC Pipeline (LUMI)

Eight self-resubmitting SLURM jobs run the pipeline unattended. Each is a persistent service or polling loop that resubmits itself on exit.

| Job | Script | Role |
|---|---|---|
| `A-restart` | `restart-services-sbatch.sh` | Cancels and resubmits all services every 12 h |
| `B-ollama` | `3-analyze/hpc/2-ollama-serve-sbatch.sh` | Persistent Ollama GPU daemon (Llama 3) |
| `C-sync` | `4-file-sync/hpc/sync-sbatch.sh` | rclone loop — Drive ↔ LUMI every 5 min |
| `D-embed` | `6-embed/hpc/1-embed-serve-sbatch.sh` | Embedding server (multilingual-e5-large) |
| `E-qdrant` | `7-index/hpc/1-qdrant-serve-sbatch.sh` | Qdrant vector DB service |
| `F-index` | `7-index/hpc/2-index-serve-sbatch.sh` | Index server — writes to Qdrant |
| `G-graph` | `9-graph/hpc/graph-sbatch.sh` | Graph + playlist generation (on demand) |
| `Z-poll` | `pipeline-hpc-poll.sh` | Pipeline poller — launches array jobs every 10 min |
| *(array)* | `pipeline-hpc-sbatch.sh` | One SLURM task per audio file (GPU) |



> **Known issue:** There is a race condition between Z-poll and running pipeline tasks — duplicate jobs can be submitted if a file has not finished processing before the next poll cycle. This is relatively harmless (the `.done` file guards against double-indexing) but could waste GPU resources if a job stalls.

### Monitoring & Management

```bash
# Active jobs
squeue --me

# Logs
tail -f logs/sync-slurm-<jobid>.out       # C-sync
tail -f logs/poll-slurm-<jobid>.out       # Z-poll
tail -f logs/<jobid>_<taskid>.out         # pipeline array tasks
tail -f logs/embed-slurm-<jobid>.out      # D-embed
tail -f logs/index-slurm-<jobid>.out      # F-index
tail -f logs/graph-slurm-<jobid>.out      # G-graph

# Manifests
cat logs/sync-manifest.txt                # files synced from Drive
cat logs/pipeline-manifest-*.txt          # files submitted for processing

# Cancel everything
scancel --me
```

## Repository Structure

| Directory / File | Description |
|---|---|
| [`1-train/`](1-train/README.md) | Whisper fine-tuning on FLEURS — SLURM GPU array, 1 job per language |
| [`2-inference/`](2-inference/README.md) | Chunked long-form audio transcription and ES→EN translation |
| [`3-analyze/`](3-analyze/README.md) | Structured metadata extraction via Llama 3 / Ollama |
| [`4-file-sync/`](4-file-sync/README.md) | Google Drive ↔ LUMI bi-directional rclone sync (5-min polling loop) |
| [`5-sentiment/`](5-sentiment/README.md) | Per-video sentiment label and score from transcript chunks |
| [`6-embed/`](6-embed/README.md) | Embedding server — `POST /embed` returns 1024-dim vectors (port 8765) |
| [`7-index/`](7-index/README.md) | Index server — `POST /index` and `POST /metadata` write to Qdrant (port 8766) |
| [`8-search/`](8-search/README.md) | Semantic nearest-neighbour search over indexed transcript chunks |
| [`9-graph/`](9-graph/README.md) | Knowledge graph builder and personalised playlist generator |
| [`pipeline.py`](pipeline.py) | End-to-end orchestrator: infer → analyze → sentiment → embed → index |
| [`pipeline.yaml`](pipeline.yaml) | Central configuration (model, server URLs, feature flags) |
| `pipeline-local.sh` | Run full pipeline locally with native Python and Ollama |
| `pipeline-docker.sh` | Run full pipeline inside Docker Compose |
| `pipeline-hpc-submit.sh` | Scan manifest and submit SLURM array jobs |
| `pipeline-hpc-sbatch.sh` | SLURM GPU task wrapper — runs `pipeline.py` inside Singularity |
| `pipeline-hpc-poll.sh` | Self-resubmitting scheduler — polls for new files every 10 minutes |
| `profiles/<user>.json` | Per-user profile for playlist personalisation |
| `roles.yaml` | Role → tag mapping used by `9-graph/playlist.py` |

## References

- [HuggingFace: Fine-Tune Whisper](https://huggingface.co/blog/fine-tune-whisper)
- [Google FLEURS Dataset](https://huggingface.co/datasets/google/fleurs)
- [intfloat/multilingual-e5-large](https://huggingface.co/intfloat/multilingual-e5-large)
- [cardiffnlp/twitter-roberta-base-sentiment-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [rclone Documentation](https://rclone.org/drive/)
