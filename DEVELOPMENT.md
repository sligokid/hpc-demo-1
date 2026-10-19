# Development Guide

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

## Launch the Pipeline Locally (Docker)

**Prerequisites:** Docker Desktop running, `rclone` installed and configured (see [`4-file-sync/README.md`](4-file-sync/README.md)).

```bash
# Start (or restart) all persistent services — ollama, qdrant, embed-server, index-server
./restart-services-docker.sh

# Rebuild images first if you've changed code
./restart-services-docker.sh --build
```

Services and ports once healthy:

| Service | Port | Dashboard | Dockerfile |
|---|---|---|---|
| `ollama` | 11434 | — | — |
| `qdrant` | 6333 | http://localhost:6333/dashboard | — |
| `embed-server` | 8765 | http://localhost:8765/health | — |
| `index-server` | 8766 | http://localhost:8766/health | — |
| `agent` | — (stdin/tty) | — | `10-agent/docker/Dockerfile` |

Then run the pipeline:

```bash
./pipeline-docker.sh
```

Start the agent (after services are running):

```bash
docker compose run --rm agent
# or locally:
bash 10-agent/local/run.sh
```

---

## Launch the Pipeline on LUMI

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

---

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

> **Agent on HPC:** The conversational agent runs interactively via `10-agent/hpc/run.sh` once B-ollama, D-embed, E-qdrant, and F-index are healthy. It is not a persistent service job.

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
