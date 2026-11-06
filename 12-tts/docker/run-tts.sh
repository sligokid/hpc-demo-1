#!/bin/bash
# Run tts.py inside Docker for a single teleprompter file.
#
# Usage (from project root):
#   bash 12-tts/docker/run-tts.sh sync/output/en/myvideo.teleprompter.md
#
# Reads:  sync/output/{lang}/{stem}.teleprompter.md   (host path; mounted at /sync/output)
# Writes: sync/output/{lang}/{stem}.teleprompter.wav
#
# Environment variables:
#   OLLAMA_HOST    host:port for Ollama   (default: ollama:11434)
#   VOICE          TTS voice name         (default: male)
#   MODEL          Ollama TTS model name  (default: lfm3-audio)
#   TTS_IMAGE      Docker image name      (default: slick-plus-tts)

set -euo pipefail

TELEPROMPTER_FILE=${1:?Usage: bash 12-tts/docker/run-tts.sh <teleprompter-file>}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

OLLAMA_HOST=${OLLAMA_HOST:-ollama:11434}
VOICE=${VOICE:-male}
MODEL=${MODEL:-lfm3-audio}
IMAGE=${TTS_IMAGE:-slick-plus-tts}

LANG=$(basename "$(dirname "$TELEPROMPTER_FILE")")
STEM=$(basename "$TELEPROMPTER_FILE" .teleprompter.md)

mkdir -p "$PROJECT_ROOT/sync/output/$LANG"

# Pull the TTS model into Ollama if not already present
if ! docker compose exec ollama ollama list 2>/dev/null | grep -q "^${MODEL}"; then
    echo "Pulling model '$MODEL' into Ollama..."
    docker compose exec ollama ollama pull "$MODEL"
fi

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
    -v "$PROJECT_ROOT/sync/output:/sync/output" \
    "$IMAGE" \
    --input       "/sync/output/$LANG/$STEM.teleprompter.md" \
    --output      "/sync/output/$LANG/$STEM" \
    --ollama-host "$OLLAMA_HOST" \
    --voice       "$VOICE" \
    --model       "$MODEL"
