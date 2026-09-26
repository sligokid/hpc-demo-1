# 3-analyze — Metadata Generation

Generates structured metadata from transcripts using Llama via Ollama. Extracts title, description, tags, goals, and skills as a JSON object written alongside the transcript.

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `llama3` | [Ollama](https://ollama.com/library/llama3) | Default model — extracts title, description, tags, goals, and skills from transcripts |
| `llama3.1:8b` | [Ollama](https://ollama.com/library/llama3.1) | Recommended for HPC — larger context window, better structured JSON output |

Model is configurable via `--model` flag or `analyze.model` in `pipeline.yaml`. Pull with `ollama pull <model>` before running.

---

## How it Works

`analyze.py` sends the full transcript text to the Ollama API as a structured prompt and asks Llama to return a JSON object. The prompt instructs the model to extract:

- **title** — concise video title inferred from content
- **description** — 2–3 sentence summary
- **tags** — list of topic keywords (used by `9-graph` for playlist ranking and graph edges)
- **goals** — learning objectives
- **skills** — skills demonstrated or discussed

The response is parsed with a JSON regex fallback in case the model wraps the output in markdown code fences. If parsing fails after retries, `analyze.py` returns a default empty metadata object so the pipeline continues rather than fails.

On HPC, a single persistent Ollama service job (`B-ollama`) serves the entire array of pipeline tasks. This avoids loading the 4–8 GB model weights once per file, which would be prohibitively slow.

---

## Sample Output

`analyze.py` returns a JSON object written to `sync/output/<lang>/<filename>.analysis.json`:

```json
{
  "title": "Unlocking the Power of Social Learning",
  "description": "This video explores how organisations can harness social and peer learning to build a culture of continuous knowledge sharing. The speaker outlines practical strategies for capturing tacit knowledge before it walks out the door.",
  "tags": ["social learning", "knowledge sharing", "organisational development", "learning culture"],
  "goals": ["Understand the value of informal knowledge transfer", "Identify opportunities to embed social learning into daily workflows"],
  "skills": ["Knowledge management", "Learning strategy", "Stakeholder engagement"]
}
```

---

## Files

| File | Role |
|------|------|
| `analyze.py` | Calls Ollama API with transcript, returns structured JSON metadata |
| `hpc/2-ollama-serve-sbatch.sh` | SLURM service job — persistent Ollama service on a GPU node |
| `hpc/3-ollama-pull-llama3.sh` | One-time manual script — pulls model weights into scratch (run from login node) |
| `hpc/analyze-batch.sh` | SLURM array job — runs analyze.py across a folder of transcripts |
| `hpc/analyze-on-gpu.sh` | Interactive `srun` wrapper for a single transcript |
| `local/` | Step-by-step scripts for running Ollama locally |
| `docker/` | Step-by-step scripts for running Ollama via Docker Compose |
| `test_analyze.py` | Unit tests for `analyze()` (mocked HTTP, no Ollama needed) |

---

## Running locally

```bash
# 1. Start Ollama
bash 3-analyze/local/1-ollama-run-llama-3.1-8b.sh

# 2. In a separate terminal — test the API then run analyze
bash 3-analyze/local/2-llama-query-api.sh
bash 3-analyze/local/3-llama-query-analyze.sh
```

---

## Docker

> Docker Desktop on macOS cannot access Apple Metal. Ollama inside Docker uses CPU inference only. For faster results, use native Ollama pointed at `localhost:11434`.

```bash
# 1. Start the Ollama service
docker compose up -d ollama

# 2. Pull the model into the named volume (once)
docker compose exec ollama ollama pull llama3

# 3. Run analyze.py inside the dev container
docker compose run --rm dev python 3-analyze/analyze.py \
    --transcript sync/output/en/my-video.transcript.txt \
    --ollama-host ollama:11434
```

---

## Running on LUMI (HPC)

A persistent Ollama service occupies one GPU node and serves the whole batch, eliminating per-task model-load overhead.

Pull the ollama.sif file first: see `../../update-sifs.sh`

**Interactive single transcript:**

```bash
./3-analyze/hpc/analyze-on-gpu.sh transcripts/foo.txt
```

**Unattended batch:**

```bash
SVC=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
N=$(find results/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) 3-analyze/hpc/analyze-batch.sh results/
```

---

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--transcript` | required | Path to transcript file, or `-` to read from stdin |
| `--model` | `llama3` | Ollama model to use |
| `--ollama-host` | `localhost:11434` | Ollama host to connect to |
