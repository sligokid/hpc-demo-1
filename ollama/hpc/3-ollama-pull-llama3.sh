#!/bin/bash
# One-time setup for air-gapped HPC operation.
# Run this once on a login node or data-transfer node with internet access
# before submitting any analysis jobs.
#
# Step 1 — build the Singularity image (once per cluster):
#   singularity pull ollama.sif docker://ollama/ollama:rocm
#   mv ollama.sif /scratch/project_465003209/mcgowank/
#
# Step 2 — start the Ollama service (must be running before this script):
#   sbatch ollama-serve.sh
#
# Step 3 — pull model weights into scratch (this script):
#   ./ollama-pull.sh [model]
#
# Examples:
#   ./ollama-pull.sh              # pulls llama3 (default)
#   ./ollama-pull.sh llama3:8b-q4
#   ./ollama-pull.sh mistral

set -euo pipefail

MODEL=${1:-llama3}

SCRATCH=${SCRATCH:-/scratch/project_465003209/mcgowank}
OLLAMA_SIF=${OLLAMA_SIF:-$SCRATCH/ollama.sif}
OLLAMA_MODELS_DIR=$SCRATCH/ollama-models

if [ ! -f "$OLLAMA_SIF" ]; then
    echo "Error: ollama.sif not found at $OLLAMA_SIF" >&2
    echo "Build it first: singularity pull ollama.sif docker://ollama/ollama:rocm" >&2
    exit 1
fi

ENDPOINT_FILE=$SCRATCH/ollama.endpoint

if [ ! -f "$ENDPOINT_FILE" ]; then
    echo "Error: endpoint file not found at $ENDPOINT_FILE" >&2
    echo "Start the Ollama service first: sbatch ollama-serve.sh" >&2
    exit 1
fi

OLLAMA_HOST=$(cat "$ENDPOINT_FILE")
echo "Using Ollama service at $OLLAMA_HOST"

mkdir -p "$OLLAMA_MODELS_DIR"

echo "Pulling model '$MODEL' into $OLLAMA_MODELS_DIR ..."

singularity exec \
    --bind "$OLLAMA_MODELS_DIR:/ollama-models" \
    --env OLLAMA_MODELS=/ollama-models \
    --env OLLAMA_HOST="$OLLAMA_HOST" \
    "$OLLAMA_SIF" \
    ollama pull "$MODEL"

echo "Verifying model is present in ollama list ..."

LIST=$(singularity exec \
    --bind "$OLLAMA_MODELS_DIR:/ollama-models" \
    --env OLLAMA_MODELS=/ollama-models \
    --env OLLAMA_HOST="$OLLAMA_HOST" \
    "$OLLAMA_SIF" \
    ollama list)

MODEL_BASE=${MODEL%%:*}
if echo "$LIST" | grep -q "^${MODEL_BASE}"; then
    echo "Model '$MODEL' is ready in $OLLAMA_MODELS_DIR."
else
    echo "Error: model '$MODEL' was not found in ollama list after pull." >&2
    echo "Output was:" >&2
    echo "$LIST" >&2
    exit 1
fi
