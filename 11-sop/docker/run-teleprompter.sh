#!/bin/bash
# Run teleprompter.py inside Docker for a single SOP file.
#
# Usage (from project root):
#   bash 11-sop/docker/run-teleprompter.sh sync/input/en/my-procedure.sop.md
#
# Reads:  sync/input/{lang}/{stem}.sop.md   (host path; mounted read-only at /sync/input)
# Writes: sync/output/{lang}/{stem}.teleprompter.md  (mounted at /sync/output)
#
# Environment variables:
#   MODEL                  Ollama model name       (default: qwen2.5:7b)
#   OLLAMA_HOST            host:port for Ollama    (default: ollama:11434)
#   TELEPROMPTER_IMAGE     Docker image name       (default: slick-plus-teleprompter)

set -euo pipefail

SOP_FILE=${1:?Usage: bash 11-sop/docker/run-teleprompter.sh <sop-file>}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODEL=${MODEL:-qwen2.5:7b}
OLLAMA_HOST=${OLLAMA_HOST:-ollama:11434}
IMAGE=${TELEPROMPTER_IMAGE:-slick-plus-teleprompter}

# Derive output stem: sync/input/{lang}/{stem}.sop.md -> sync/output/{lang}/{stem}
LANG=$(basename "$(dirname "$SOP_FILE")")
STEM=$(basename "$SOP_FILE" .sop.md)
STEM=$(basename "$STEM" .md)

mkdir -p "$PROJECT_ROOT/sync/output/$LANG"

# Build the image if it doesn't exist yet
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    echo "Image '$IMAGE' not found — building..."
    docker build \
        -f "$SCRIPT_DIR/Dockerfile" \
        -t "$IMAGE" \
        "$PROJECT_ROOT"
fi

docker run --rm \
    --network hpc-demo-1_default \
    -v "$PROJECT_ROOT/sync/input:/sync/input:ro" \
    -v "$PROJECT_ROOT/sync/output:/sync/output" \
    "$IMAGE" \
    --sop         "/sync/input/$LANG/$STEM.sop.md" \
    --output      "/sync/output/$LANG/$STEM" \
    --ollama-host "$OLLAMA_HOST" \
    --model       "$MODEL"
