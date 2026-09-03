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

See [`3-analyze/README.md`](3-analyze/README.md) for full instructions — local, Docker, and HPC Ollama batch pipeline.

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
│  transcript  ──►  3-analyze/analyze.py  ──►  metadata (JSON)      │
│                   (llama3)         title, description,  │
│                                    tags, goals, skills  │
└─────────────────────────────────────────────────────────┘
```

## Automated HPC Pipeline

The full pipeline (transcription → metadata generation) can run automatically on HPC with no manual intervention. Two self-resubmitting SLURM jobs handle file delivery and processing:

```
Google Drive                  LUMI HPC
─────────────                 ────────────────────────────────────────
whisper-sync/                 4-file-sync/hpc/submit-sync.sh  (every 10 min)
  input/   ── rclone copy ──► inbox/
  output/  ◄─ rclone copy ── results/

                              pipeline-hpc-poll.sh  (every 10 min)
                              └─► pipeline-hpc-submit.sh
                                  └─► pipeline-hpc-sbatch.sh (array job, 1 GPU per file)
                                      ├─► 2-inference/infer.py   (Whisper transcription)
                                      └─► 3-analyze/analyze.py   (Ollama metadata)
```

### Start the automated pipeline on LUMI

**Prerequisites:** Singularity images built and in scratch, rclone config copied to LUMI.

```bash
cd /scratch/project_465003209/mcgowank/hpc-demo-1

# 1. Start the Ollama inference service (self-resubmits every 8 hours)
sbatch 3-analyze/hpc/2-ollama-serve-sbatch.sh

# 2. Start the file sync loop (polls Google Drive every 10 minutes)
cd 4-file-sync/hpc && sbatch submit-sync.sh && cd ../..

# 3. Start the pipeline poller (submits jobs for new files every 10 minutes)
sbatch pipeline-hpc-poll.sh
```

All three jobs are now running. Ollama must be ready before the pipeline poller submits work — check `squeue` and wait for the Ollama job to move from `PD` to `R` before dropping files into Drive. Drop audio or video files into `whisper-sync/input/` in Google Drive — they will be picked up, transcribed, and analysed automatically. Results appear in `whisper-sync/output/`.

### Monitor

```bash
squeue -u $USER                                  # see both polling jobs + any pipeline array jobs
tail -f logs/sync-slurm-<jobid>.out             # sync loop log
tail -f logs/poll-slurm-<jobid>.out             # pipeline poller log
tail -f logs/<arrayjobid>_<taskid>.out          # individual file processing log
cat logs/sync-manifest.txt                       # files received from Drive
```

### Stop everything

```bash
scancel -u $USER
```

### File sync setup

See [`4-file-sync/setup.md`](4-file-sync/setup.md) for one-time rclone + Google Drive OAuth2 setup, Docker image build, SIF conversion, and cloud provider swap instructions (GCS, S3).

## How it works

See [`1-train/README.md`](1-train/README.md) for details on the training pipeline.

### How translation works — and why it has limits

See [`2-inference/README.md`](2-inference/README.md) for details on translation mode, constraints, and example output.


## References:
https://huggingface.co/blog/fine-tune-whisper
https://www.learn-spanish-faster.com/articles/spanish-phrases-free-mp3-download.html

