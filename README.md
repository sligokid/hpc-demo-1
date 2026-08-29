# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning for ASR

**Goal: Turning videos into machine-readable knowledge**

Fine-tunes `openai/whisper-small` on [Google FLEURS](https://huggingface.co/datasets/google/fleurs) across five languages simultaneously using a SLURM job array on HPC GPU infrastructure. Demonstrates how multilingual speech model training that would take weeks on standard infrastructure can be reduced to days.

## Languages

| Code | Language | FLEURS locale |
|------|----------|---------------|
| `en` | English | `en_us` |
| `es` | Spanish | `es_419` |
| `fr` | French | `fr_fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` |
| `ar` | Arabic | `ar_eg` |

## Setup

### Linux / Mac (Apple Silicon) — local dev

Run directly in a virtualenv. PyTorch's MPS backend is used automatically; Docker cannot access it.

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### Docker Build <a name="build"></a> — local dev
**To build and push a new image** (run locally with Docker installed):

```bash
docker build -t sligokid/hpc-demo-1:latest .
docker push sligokid/hpc-demo-1:latest
```
**To build update and push a new image with amd64 support** edit `requirements.txt` or the `Dockerfile`, then rebuild and push:

```bash
docker buildx build --platform linux/amd64 -t sligokid/whisper-hpc:latest --push .
```

### Singularity Build from Docker image (AMD/ROCm) - HPC

Pull the docker image once on the login node 

```bash
singularity pull ~/whisper-hpc.sif docker://sligokid/hpc-demo-1:latest
```
#### Set cache directories when using Docker containers

When pulling or building from Docker containers using singularity, the conversion can be quite heavy. Speed up the conversion and avoid leaving behind temporary files by using the in-memory filesystem on /tmp as the Singularity cache directory, 

i.e. On the worker node
```bash
$ mkdir -p /tmp/$USER
$ export SINGULARITY_TMPDIR=/tmp/$USER
$ export SINGULARITY_CACHEDIR=/tmp/$USER
singularity pull whisper-hpc.sif docker://sligokid/whisper-hpc:latest
```
## Training <a name="training"></a>

See [`1-train/README.md`](1-train/README.md) for full training instructions, smoke tests, HPC submission, and how to extend the pipeline.

## Inference

See [`2-inference/README.md`](2-inference/README.md) for full inference instructions, translation mode, HPC scripts, and example output.

## Metadata Generation

`analyze.py` takes a transcript and calls an Ollama LLM to extract structured metadata (title, description, tags, goals, skills).

### Local — native Ollama on GPU 

Serve llama
```bash
ollama serve          # in a separate terminal, if not already running
ollama pull llama3.1:8b # once

# OR instead 
ollama run llama3.1:8b
```

Query llama
```bash
python analyze.py --transcript transcripts/my-video.txt
```

Pipe from `infer.py` directly:

```bash
python 2-inference/infer.py --model_dir checkpoints/en --audio my-talk.mp3 | \
    python analyze.py --transcript -
```

### Local — Docker Compose on CPU only (no native Ollama install required)

```bash
# 1. Start the Ollama service
docker compose up -d ollama

# 2. Pull the model into the named volume (once)
docker compose exec ollama ollama pull llama3

# 3-a. Run analyze.py inside the dev container
docker compose run --rm dev python analyze.py     --transcript results/infer-on-gpu.sh.txt     --ollama-host ollama:11434

# 3-b. Run analyze.py against ollama runnning in a docker container
python analyze.py     --transcript results/infer-on-gpu.sh.txt

# 3-c Run analyze.py against ollama runnning locally
python analyze.py     --transcript results/infer-on-gpu.sh.txt --model llama3.1:8b
```

The `ollama_models` named volume persists model weights across restarts. Re-running step 2 after the model is cached is safe and fast.

> **Note:** Docker Desktop on macOS cannot access Apple Metal (MPS). Ollama inside Docker uses CPU inference only. For faster results, use native Ollama (`ollama serve`) and point `analyze.py` at `localhost:11434` (the default).

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--transcript` | required | Path to transcript file, or `-` to read from stdin |
| `--model` | `llama3` | Ollama model to use |
| `--ollama-host` | `localhost:11434` | Ollama host to connect to |

### Swap the model

Any model pulled into the named volume can be used:

```bash
docker compose exec ollama ollama pull mistral
docker compose run --rm dev python analyze.py \
    --transcript transcripts/my-video.txt \
    --ollama-host ollama:11434 \
    --model mistral
```

### HPC — Ollama on GPU node (AMD/ROCm)

Runs `analyze.py` at scale: a persistent Ollama service occupies one GPU node and serves
the whole batch, eliminating per-task model-load overhead (~30–60 s each).

#### Prerequisites — build `ollama.sif` once

On a login node or data-transfer node with internet access:

```bash
# Set cache dirs to avoid leaving temp files on the login node
mkdir -p /tmp/$USER
export SINGULARITY_TMPDIR=/tmp/$USER
export SINGULARITY_CACHEDIR=/tmp/$USER

singularity pull ollama.sif docker://ollama/ollama:rocm
mv ollama.sif /scratch/project_465003209/$USER/
```

#### Step 1 — pull model weights into scratch (once, before air-gapped compute)

Run on any node with internet access while the Ollama service is already running:

```bash
./ollama/hpc/3-ollama-pull.sh              # pulls llama3 (default)
./ollama/hpc/3-ollama-pull.sh llama3:8b-q4 # or a quantised variant
```

The script verifies the model is present in `ollama list` before exiting.

#### Step 2 — start the persistent Ollama service

```bash
mkdir -p logs
SVC=$(sbatch --parsable ollama/hpc/2-ollama-serve-sbatch.sh)
echo "Service job: $SVC"
```

The job writes `hostname:11434` to the endpoint discovery file in scratch once the
HTTP health check passes. It removes the file on exit (wall-time expiry or `scancel`).

#### Step 3 — submit the batch analysis array

```bash
N=$(find transcripts/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) analyze-batch.sh transcripts/
```

Each task reads the endpoint file, calls `analyze.py --transcript <file> --ollama-host
<endpoint>`, and writes JSON to `metadata/<basename>.json`.

#### Interactive single-transcript (srun wrapper)

```bash
./analyze-on-gpu.sh transcripts/foo.txt
```

#### Unattended overnight pipeline — chain all steps in one command

```bash
# 1. Start the Ollama service and capture the job ID
SVC=$(sbatch --parsable ollama/hpc/2-ollama-serve-sbatch.sh)

# 2. Submit batch analysis — starts only after the service job is allocated
N=$(find transcripts/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) analyze-batch.sh transcripts/

echo "Service job $SVC — analysis array queued behind it"
```

#### Directory layout

```
/scratch/project_465003209/<user>/
    ollama.sif          # Ollama Singularity image (built once)
    ollama-models/      # GGUF weight cache (written by ollama-pull.sh)
    ollama.endpoint     # hostname:port — created on service start, removed on exit

$PWD/
    transcripts/        # input:  one .txt per video (from infer.py)
    metadata/           # output: one .json per transcript (from analyze.py)
    logs/               # SLURM stdout/stderr  (%A_%a.out convention)
```

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────┐
│  TRAINING  (HPC — 5 parallel SLURM jobs)                │
│                                                         │
│  Google FLEURS  ──►  1-train/train.py  ──►  checkpoints/<lang>  │
│  (en, es, fr,         x5 GPUs                           │
│   zh-CN, ar)          in parallel                       │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  TRANSCRIPTION  (local or HPC)                          │
│                                                         │
│  audio file  ──►  2-inference/infer.py  ──►  transcript (text)      │
│                   (Whisper)                             │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  METADATA GENERATION  (local — Ollama)                  │
│                                                         │
│  transcript  ──►  analyze.py  ──►  metadata (JSON)      │
│                   (llama3)         title, description,  │
│                                    tags, goals, skills  │
└─────────────────────────────────────────────────────────┘
```

## How it works

See [`1-train/README.md`](1-train/README.md) for details on the training pipeline.

### How translation works — and why it has limits

See [`2-inference/README.md`](2-inference/README.md) for details on translation mode, constraints, and example output.


## References:
https://huggingface.co/blog/fine-tune-whisper
https://www.learn-spanish-faster.com/articles/spanish-phrases-free-mp3-download.html

