# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning & Knowledge Extraction Pipeline

**Goal: Turning speech & video into machine-readable knowledge at HPC scale.**

Fine-tunes `openai/whisper-small` on [Google FLEURS](https://huggingface.co/datasets/google/fleurs) across five languages simultaneously using SLURM GPU job arrays on HPC infrastructure, transcribes audio/video files, extracts structured JSON metadata via Llama 3 (Ollama), and synchronises files bi-directionally with Google Drive (or GCS/S3) via rclone.

```
  ┌─────────────────────────────────────────────────────────┐
  │                    STAGE 1: TRAINING                    │
  │   Fine-tune Whisper (GPU) on Google FLEURS              │
  │   en, es, fr, zh-CN, ar (5 parallel SLURM tasks)        │
  └────────────────────────────┬────────────────────────────┘
                               │  
                               ▼
                      checkpoints/<lang>

─────────────────────────────────────────────────────────────

  ┌─────────────────────┐
  │   Google Drive      │◄── [ Upload mp3/mp4/wav/flac/m4a/ogg ]
  │  whisper-sync/input │
  └──────────┬──────────┘
             │  rclone (every 5 min via sync-sbatch.sh)
             ▼
  ┌─────────────────────┐
  │   LUMI HPC Scratch  │
  │     sync/input/     │
  └──────────┬──────────┘
             │  pipeline-hpc-poll.sh (every 10 min)
             ▼
  ┌─────────────────────┐
  │ STAGE 2: TRANSCRIBE │
  │ Whisper (AMD/ROCm)  │──► sync/output/<lang>/<stem>.transcript.txt
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  STAGE 3: EXTRACT   │
  │  Llama 3 via Ollama │──► sync/output/<lang>/<stem>.analysis.json
  │  (GPU daemon)       │    (title, description, tags, goals, skills)
  └──────────┬──────────┘
             │  rclone (every 5 min via sync-sbatch.sh)
             ▼
  ┌─────────────────────┐
  │   Google Drive      │◄── [ Download Transcripts & Metadata JSON ]
  │  whisper-sync/output│
  └─────────────────────┘
```

---

## Repository Structure

| Directory / File | Description |
|---|---|
| [`1-train/`](1-train/README.md) | Whisper fine-tuning on FLEURS (local, Docker, and HPC SLURM array jobs) |
| [`2-inference/`](2-inference/README.md) | Audio transcription and ES→EN translation (`infer.py`, chunked 30s processing) |
| [`3-analyze/`](3-analyze/README.md) | Structured metadata extraction using Llama 3 via Ollama API (`analyze.py`) |
| [`4-file-sync/`](4-file-sync/README.md) | Bi-directional cloud file sync with Google Drive / S3 / GCS via rclone |
| [`pipeline.py`](pipeline.py) | End-to-end Python pipeline orchestrator (processes `sync/input` → `sync/output`) |
| [`pipeline.yaml`](pipeline.yaml) | Central pipeline configuration file |
| `pipeline-local.sh` | Run the full pipeline locally with native Python & Ollama |
| `pipeline-docker.sh` | Run the full pipeline locally inside Docker Compose |
| `pipeline-hpc-submit.sh` | Generate manifest and submit SLURM array jobs on HPC |
| `pipeline-hpc-sbatch.sh` | SLURM GPU task wrapper executing `pipeline.py` inside Singularity SIF |
| `pipeline-hpc-poll.sh` | Self-resubmitting scheduler polling for new files every 10 minutes |

---

## Supported Languages

| Code | Language | FLEURS Locale | Checkpoint Path |
|---|---|---|---|
| `en` | English | `en_us` | `checkpoints/en` |
| `es` | Spanish | `es_419` | `checkpoints/es` |
| `fr` | French | `fr_fr` | `checkpoints/fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` | `checkpoints/zh` |
| `ar` | Arabic | `ar_eg` | `checkpoints/ar` |

---

## Automated HPC Pipeline (LUMI)

The full end-to-end processing pipeline runs unattended on LUMI HPC using self-resubmitting SLURM jobs:

```
Google Drive                      LUMI HPC Scratch
────────────                      ─────────────────────────────────────────────────
whisper-sync/                     4-file-sync/hpc/sync-sbatch.sh (every 5 min)
  input/   ─── rclone copy ────►  sync/input/
  output/  ◄── rclone copy ─────  sync/output/

                                  pipeline-hpc-poll.sh (every 10 min)
                                  └─► pipeline-hpc-submit.sh
                                      └─► pipeline-hpc-sbatch.sh (1 GPU per audio file)
                                          ├─► 2-inference/infer.py  (Whisper transcription)
                                          └─► 3-analyze/analyze.py  (Ollama Llama 3 metadata)
```

### 1. Launch the Automated Loop on LUMI

**Prerequisites:** Singularity containers built in scratch (`whisper-hpc.sif`, `whisper-sync.sif`, `ollama.sif`) and rclone config copied to `~/.config/rclone/rclone.conf`.

```bash
cd /scratch/project_465003209/mcgowank/hpc-demo-1

# 1. Start the persistent Ollama GPU service (self-resubmits every 8 hours)
sbatch 3-analyze/hpc/2-ollama-serve-sbatch.sh

# 2. Start the file sync loop (polls Google Drive every 5 minutes)
sbatch 4-file-sync/hpc/sync-sbatch.sh

# 3. Start the pipeline poller (scans sync/input/ and launches jobs every 10 minutes)
sbatch pipeline-hpc-poll.sh
```

> **Note:** Wait for the Ollama job to move from `PD` (pending) to `R` (running) and write `/scratch/project_465003209/mcgowank/ollama.endpoint` before processing starts.

### 2. Manual Batch Submission (On-Demand)

To process pending files immediately without waiting for the poller:

```bash
# Process all pending files across all languages
./pipeline-hpc-submit.sh

# Restrict to a specific language
./pipeline-hpc-submit.sh --lang en

# Chain with Ollama service job ID
JID=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
./pipeline-hpc-submit.sh --dependency after:$JID
```

### 3. Monitoring & Management

```bash
# View active and queued SLURM jobs
squeue -u $USER

# Monitor logs
tail -f logs/sync-slurm-<jobid>.out             # File sync log
tail -f logs/poll-slurm-<jobid>.out             # Pipeline poller log
tail -f logs/<jobid>_<taskid>.out               # Individual file processing log

# Check manifests
cat logs/sync-manifest.txt                      # Files synced from Google Drive
cat logs/pipeline-manifest-*.txt                # Files submitted for HPC processing

# Cancel all user jobs
scancel -u $USER
```

---

## Local Development & Testing

### Setup Native Environment (macOS / Linux)

PyTorch uses Apple Silicon MPS or Linux CUDA automatically.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Full Pipeline Locally

Start Ollama in a separate terminal:
```bash
ollama serve
ollama pull llama3.1:8b  # or llama3
```

Run the pipeline orchestrator:
```bash
# Process all audio files in sync/input/
./pipeline-local.sh

# Or run pipeline.py with options
python pipeline.py --lang en
python pipeline.py --file sync/input/en/sample.mp3 --ollama-host localhost:11434
```

Quick one-line pipe demo:
```bash
bash pipeline-demo-local.sh
```

### Run via Docker Compose

**To build update and push a new image with amd64 support** edit `requirements.txt` or the `Dockerfile`, then rebuild and push:

```bash
# Local development image
docker build -t sligokid/hpc-demo-1:latest .

# Multi-arch amd64 image for HPC deployment
docker buildx build --platform linux/amd64 -t sligokid/whisper-hpc:latest --push .
```

### 2. Convert Whisper Image(`whisper-hpc`) to Singularity SIF (HPC)

On LUMI worker node (using memory-backed cache in `/tmp`):

```bash
mkdir -p /tmp/$USER
export SINGULARITY_TMPDIR=/tmp/$USER
export SINGULARITY_CACHEDIR=/tmp/$USER

singularity pull /scratch/project_465003209/mcgowank/whisper-hpc.sif docker://sligokid/whisper-hpc:latest
```

### 3. Build & Convert Cloud Sync Image (`whisper-sync`)

```bash
# Build amd64 sync image locally and push
docker buildx build --platform linux/amd64 -t sligokid/whisper-sync:latest --push 4-file-sync/

# Pull SIF on LUMI
singularity pull /scratch/project_465003209/mcgowank/whisper-sync.sif docker://sligokid/whisper-sync:latest
```

### 4. Pull Ollama ROCm SIF (HPC) Image (`ollama`)

```bash
singularity pull /scratch/project_465003209/mcgowank/ollama.sif docker://ollama/ollama:rocm
```

---

## Testing

```bash
# Run Python unit tests for infer & analyze
pytest 2-inference/test_infer.py
pytest 3-analyze/test_analyze.py

# Run mock sync smoke tests
bash 4-file-sync/test-sync.sh

# Run shell script test suite (BATS)
make test
```

---

## Component Documentation

- **[Stage 1 — Training](1-train/README.md):** FLEURS dataset fine-tuning, SLURM GPU job arrays, hyperparameter configs, evaluation metrics (WER).
- **[Stage 2 — Inference & Translation](2-inference/README.md):** Chunked long-form audio transcription, translation mode, interactive GPU/CPU execution.
- **[Stage 3 — Metadata Extraction](3-analyze/README.md):** Ollama daemon setup on AMD/ROCm GPU, prompt formatting, structured JSON extraction.
- **[Stage 4 — Cloud Sync](4-file-sync/README.md):** Google Drive OAuth2 setup, rclone configuration, automated 5-minute sync loop, and cloud provider swapping (GCS/S3).

---

## References

- [HuggingFace: Fine-Tune Whisper with 🤗 Transformers](https://huggingface.co/blog/fine-tune-whisper)
- [Google FLEURS Dataset](https://huggingface.co/datasets/google/fleurs)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [rclone Documentation](https://rclone.org/drive/)


