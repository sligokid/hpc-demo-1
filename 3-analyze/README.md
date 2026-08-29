# Metadata Generation — Analyze transcripts with Ollama

`analyze.py` takes a transcript and calls an Ollama LLM to extract structured metadata: title, description, tags, goals, and skills.

## Running

### Local — native Ollama

```bash
ollama serve &          # start in background
ollama pull llama3.1:8b # once

python 3-analyze/analyze.py --transcript transcripts/my-video.txt --model llama3.1:8b
```

Pipe directly from inference:

```bash
python 2-inference/infer.py --model_dir checkpoints/en --audio my-talk.mp3 | \
    python 3-analyze/analyze.py --transcript -
```

See `local/` for step-by-step scripts.

### Docker — CPU only

```bash
# 1. Start the Ollama service
docker compose up -d ollama

# 2. Pull the model into the named volume (once)
docker compose exec ollama ollama pull llama3

# 3. Run analyze.py inside the dev container
docker compose run --rm dev python 3-analyze/analyze.py \
    --transcript results/infer-on-gpu.sh.txt \
    --ollama-host ollama:11434
```

> Docker Desktop on macOS cannot access Apple Metal. Ollama inside Docker uses CPU inference only. For faster results, use native Ollama and point `analyze.py` at `localhost:11434` (the default).

See `docker/` for step-by-step scripts.

### HPC — Ollama on GPU node (AMD/ROCm)

A persistent Ollama service occupies one GPU node and serves the whole batch, eliminating per-task model-load overhead.

#### Step 0 — build `ollama.sif` once

```bash
mkdir -p /tmp/$USER
export SINGULARITY_TMPDIR=/tmp/$USER
export SINGULARITY_CACHEDIR=/tmp/$USER
singularity pull ollama.sif docker://ollama/ollama:rocm
mv ollama.sif /scratch/project_465003209/$USER/
```

#### Step 1 — pull model weights into scratch

```bash
./3-analyze/hpc/3-ollama-pull-llama3.sh
```

#### Step 2 — start the persistent Ollama service

```bash
mkdir -p logs
SVC=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
echo "Service job: $SVC"
```

#### Step 3 — submit the batch analysis array

```bash
N=$(find transcripts/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) 3-analyze/hpc/analyze-batch.sh transcripts/
```

#### Interactive single transcript

```bash
./3-analyze/hpc/analyze-on-gpu.sh transcripts/foo.txt
```

#### Unattended overnight pipeline

```bash
SVC=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
N=$(find transcripts/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) 3-analyze/hpc/analyze-batch.sh transcripts/
echo "Service job $SVC — analysis array queued behind it"
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--transcript` | required | Path to transcript file, or `-` to read from stdin |
| `--model` | `llama3` | Ollama model to use |
| `--ollama-host` | `localhost:11434` | Ollama host to connect to |

## Tests

```bash
pytest 3-analyze/test_analyze.py
```

## Files

| File | Role |
|------|------|
| `analyze.py` | Calls Ollama API with transcript, returns structured JSON metadata |
| `hpc/analyze-batch.sh` | SLURM array job — runs analyze.py across a folder of transcripts |
| `hpc/analyze-on-gpu.sh` | Interactive `srun` wrapper for a single transcript |
| `local/` | Step-by-step scripts for running Ollama locally |
| `docker/` | Step-by-step scripts for running Ollama via Docker Compose |
| `hpc/` | SLURM scripts: serve Ollama, pull model, batch analyze, single transcript |
| `test_analyze.py` | Unit tests for `analyze()` (mocked HTTP, no Ollama needed) |
