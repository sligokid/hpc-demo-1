# Metadata Generation — Analyze transcripts with llama

Generate metadata from transcripts using Llama 3.1 8B via Ollama in JSON format.
Metadata includes: title, description, tags, goals, and skills.

## Running

### Local — native Llama via Ollama installed locally

Run from the local/ directory:

```bash
bash 1-ollama-run-llama-3.1-8b.sh

```
In a separate terminal
```bash
bash 2-llama-query-api.sh
bash 3-llama-query-analyze.sh
```

### Docker — CPU only
> Docker Desktop on macOS cannot access Apple Metal. Ollama inside Docker uses CPU inference only. For faster results, use native Ollama and point `analyze.py` at `localhost:11434` (the default).

Run from the docker/ directory.

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
### HPC — Ollama on GPU node (AMD/ROCm)

A persistent Ollama service occupies one GPU node and serves the whole batch, eliminating per-task model-load overhead.

Pull the ollama.sif file first: see `../../update-sifs.sh`

See hpc/ for step-by-step instructions.

#### Interactive single transcript

```bash
./3-analyze/hpc/analyze-on-gpu.sh transcripts/foo.txt
```

#### Unattended overnight pipeline

```bash
SVC=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
N=$(find results/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) 3-analyze/hpc/analyze-batch.sh results/
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
