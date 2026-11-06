# 12-tts — Teleprompter to Speech

Converts a `.teleprompter.md` file into a spoken WAV audio file using the `lfm3-audio` TTS model via Ollama.

Reads the Audio fields from each section of the teleprompter script, strips visual cues, headings, and the SME Review Checklist, then sends the cleaned text to Ollama in sentence-boundary chunks and concatenates the returned WAV segments into a single output file.

---

## Model Used

| Model | Source | Role |
|-------|--------|------|
| `lfm3-audio` | Ollama | Text-to-speech — converts presenter script text to WAV audio |

### Load the model

**Local / Docker:**

```bash
ollama pull lfm3-audio
```

**HPC (LUMI) — Ollama running inside Singularity:**

```bash
# Wait for B-ollama to reach Running state, then pull via its endpoint file
OLLAMA_HOST=$(cat /scratch/project_465003359/mcgowank/ollama.endpoint)
curl -X POST "http://$OLLAMA_HOST/api/pull" -d '{"name":"lfm3-audio"}'
```

The HPC submit script (`tts-hpc-submit.sh`) checks for the model automatically and pulls it if missing before submitting any jobs.

---

## How it Works

```
.teleprompter.md
      |
  extract_audio_text()   -- strips headings, VISUAL: cues, checklist, [PAUSE] markers
      |
  chunk_text()           -- splits at sentence boundaries (<=4096 chars per chunk)
      |
  _call_tts() x N        -- POST /v1/audio/speech to Ollama lfm3-audio
      |
  _concat_wavs()         -- merges PCM frames into a single valid WAV
      |
.teleprompter.wav
```

Generation is idempotent — if the output WAV already exists it is not regenerated.

---

## Files

| File | Role |
|------|------|
| `tts.py` | Core TTS pipeline — extract, chunk, call Ollama, concatenate WAV |
| `requirements.txt` | Python dependencies (`requests`) |
| `test_tts.py` | Unit tests (mocked Ollama HTTP calls) |
| `local/run.sh` | Local runner for a single teleprompter file |
| `docker/Dockerfile` | CPU-only image — `python:3.11-slim` + `tts.py` |
| `docker/run-tts.sh` | Docker runner — mounts `sync/output/`, calls Ollama service |
| `hpc/tts-hpc-submit.sh` | Scans `sync/output/*/` for pending `.teleprompter.md`, writes manifest, submits SLURM array |
| `hpc/tts-hpc-poll.sh` | 10-min polling loop — resubmits when new teleprompter files arrive |
| `hpc/tts-sbatch.sh` | SLURM array task — runs `tts.py` via Singularity (`tts-tools.sif`) |

---

## Running Locally

```bash
# Prerequisites
ollama pull lfm3-audio
ollama serve

# Run for a single file
bash 12-tts/local/run.sh results/en/myvideo.teleprompter.md
# Writes: results/en/myvideo.teleprompter.wav
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `localhost:11434` | Ollama host:port |
| `VOICE` | `male` | TTS voice name |
| `MODEL` | `lfm3-audio` | Ollama TTS model |

```bash
VOICE=female OLLAMA_HOST=localhost:11434 bash 12-tts/local/run.sh results/en/myvideo.teleprompter.md
```

Or call `tts.py` directly:

```bash
python 12-tts/tts.py \
    --input   results/en/myvideo.teleprompter.md \
    --output  results/en/myvideo \
    --ollama-host localhost:11434 \
    --voice   male \
    --model   lfm3-audio
```

---

## Docker

```bash
# 1. Start services (Ollama must be running)
docker compose up -d ollama

# 2. Pull the TTS model into Ollama (once)
docker compose exec ollama ollama pull lfm3-audio

# 3. Run TTS for a single file
bash 12-tts/docker/run-tts.sh sync/output/en/myvideo.teleprompter.md
# Writes: sync/output/en/myvideo.teleprompter.wav
```

The Docker runner builds the `slick-plus-tts` image automatically on first use. Override with `TTS_IMAGE=<name>`.

---

## Running on LUMI (HPC)

**Prerequisites:** `tts-tools.sif` in scratch, `B-ollama` service running, `lfm3-audio` pulled (see above).

**One-shot submit:**

```bash
bash 12-tts/hpc/tts-hpc-submit.sh
```

Scans `sync/output/*/` for `.teleprompter.md` files whose `.teleprompter.wav` does not yet exist, writes a timestamped manifest to `logs/`, and submits a SLURM array job (one task per file).

**Persistent poll loop (unattended):**

```bash
sbatch 12-tts/hpc/tts-hpc-poll.sh
```

Checks for new teleprompter files every 10 minutes and submits array jobs as they arrive. Stop with:

```bash
scancel --name=H-tts --user=$USER
```

**Monitor:**

```bash
squeue -u $USER
tail -f logs/tts-poll-<jobid>.out
tail -f logs/<jobid>_<taskid>.out
```

---

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | required | Path to `.teleprompter.md` file |
| `--output` | required | Output stem (e.g. `results/en/myvideo`) |
| `--ollama-host` | `localhost:11434` | Ollama host:port |
| `--voice` | `male` | TTS voice name passed to `lfm3-audio` |
| `--model` | `lfm3-audio` | Ollama TTS model name |
