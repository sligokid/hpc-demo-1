# 10-agent — HPC

How to build the SIF and run the agent in an interactive Singularity session on LUMI.

---

## Prerequisites

1. Docker image built locally (see `10-agent/docker/README.md`):
   ```bash
   bash 10-agent/docker/build.sh
   ```

2. Ollama running on the target node with `qwen2.5:7b` pulled (see below).

---

## Pull Docker image and convert it to SIF

Run once on a machine with Docker:

```bash
bash update-docker-repos.sh
```

Run once on a HPC node with Singularity installed:

```bash
bash update-sifs.sh
```

---

## Pull the Qwen model (first time only)

The Ollama service (`3-analyze/hpc/2-ollama-serve-sbatch.sh`) starts the server but does **not** pull any models. Both models must be pulled once after Ollama is healthy:

- `llama3` — used by the analysis pipeline (`3-analyze`)
- `qwen2.5:7b` — used by the agent for tool-calling and summarisation

The endpoint is written to `/scratch/project_465003359/mcgowank/ollama.endpoint` when ready.

```bash
# Read the endpoint written by the Ollama job
OLLAMA_ENDPOINT=$(cat /scratch/project_465003359/mcgowank/ollama.endpoint)

# Pull both models via HTTP
curl "http://${OLLAMA_ENDPOINT}/api/pull" -d '{"name":"llama3"}'
curl "http://${OLLAMA_ENDPOINT}/api/pull" -d '{"name":"qwen2.5:7b"}'
```

Or if you have an interactive session on the same node as Ollama:

```bash
export OLLAMA_HOST=localhost:11434
ollama pull llama3
ollama pull qwen2.5:7b
```

Models are stored in `$SCRATCH/ollama-models` (bind-mounted into the Ollama container) and only need to be pulled once per Ollama volume.

---

## Run the agent on HPC

Start an interactive session, set the service endpoints, then launch:

```bash
srun --pty --account project_465003359 --partition=small-g --gres=gpu:1 bash

export QDRANT_HOST=localhost:6333
export OLLAMA_HOST=localhost:11434

bash 10-agent/hpc/run.sh
```

Type a question at the `>` prompt. Type `exit` to quit.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost:6333` | Qdrant host:port |
| `OLLAMA_HOST` | `localhost:11434` | Ollama host:port |
| `AGENT_MODEL` | `qwen2.5:7b` | Ollama model name |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | HuggingFace embed model |
| `HF_HOME` | `/root/.cache/huggingface` | Model cache path inside container |

All variables are optional — defaults are used if not set.

---

## Notes

- `PROJECT_ROOT` is resolved from the script's own location (`BASH_SOURCE`), so the script works when called from the project root or from inside `10-agent/hpc/`.
- `.hf_cache/` is bind-mounted so the HuggingFace model is only downloaded once.
- The `bash -c "export LD_LIBRARY_PATH=..."` wrapper ensures ROCm GPU libraries are available inside the container (same pattern used by `2-inference/hpc/`).
