#!/bin/bash
# One-time model pull into scratch storage for air-gapped HPC operation.
# Run this once on a login node or data-transfer node with internet access
# before submitting any analysis jobs.
#
# Usage:
#   ./ollama-pull.sh [model]
#
# Examples:
#   ./ollama-pull.sh              # pulls llama3 (default)
#   ./ollama-pull.sh llama3:8b-q4
#   ./ollama-pull.sh mistral

set -euo pipefail

MODEL=${1:-llama3}

SCRATCH=/scratch/project_465003209/mcgowank
OLLAMA_SIF=${OLLAMA_SIF:-$SCRATCH/ollama.sif}
OLLAMA_MODELS_DIR=$SCRATCH/ollama-models

mkdir -p "$OLLAMA_MODELS_DIR"

echo "Pulling model '$MODEL' into $OLLAMA_MODELS_DIR ..."

singularity exec \
    --bind "$OLLAMA_MODELS_DIR:/ollama-models" \
    --env OLLAMA_MODELS=/ollama-models \
    "$OLLAMA_SIF" \
    ollama pull "$MODEL"

echo "Verifying model is present in ollama list ..."

LIST=$(singularity exec \
    --bind "$OLLAMA_MODELS_DIR:/ollama-models" \
    --env OLLAMA_MODELS=/ollama-models \
    "$OLLAMA_SIF" \
    ollama list)

# Strip optional tag for matching (e.g. "llama3:8b-q4" → "llama3")
MODEL_BASE=${MODEL%%:*}

if echo "$LIST" | grep -q "^${MODEL_BASE}"; then
    echo "Model '$MODEL' is ready in $OLLAMA_MODELS_DIR."
    exit 0
else
    echo "Error: model '$MODEL' was not found in 'ollama list' after pull." >&2
    echo "Output was:" >&2
    echo "$LIST" >&2
    exit 1
fi
